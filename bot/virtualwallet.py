import logging
import json
import requests
import redis
import asyncio
from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher, filters
from aiogram.utils.executor import start_webhook
from aiogram.dispatcher.webhook import SendMessage
from aiogram.utils.markdown import escape_md
from bot.settings import (TELEGRAM_BOT, HEROKU_APP_NAME,
                          WEBHOOK_URL, WEBHOOK_PATH,
                          WEBAPP_HOST, WEBAPP_PORT, REDIS_URL)
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
import aiogram.utils.markdown as md
from aiogram.types import ParseMode
from .bot import bot, dp, r, get_change_label
from .prices import get_price, round_sense
from .user import get_user_price_config

SCORE_KEY = "{chat_id}_bagscore_{user_id}"

# States
class Form(StatesGroup):
    coin = State()
    price_usd = State()
    price_btc = State()
    balance = State()
    spent = State()  # Will be represented in storage as 'Form:spent'

class SaleForm(StatesGroup):
    coin = State()
    price_usd = State()
    price_btc = State()
    sale_price_usd = State()
    sale_price_btc = State()
    available_coins = State()  # Will be represented in storage as 'Form:available_coins'
    coins = State()  # Will be represented in storage as 'Form:coins'

class SaleFormPercentage(StatesGroup):
    coin = State()
    price_usd = State()
    price_btc = State()
    sale_price_usd = State()
    sale_price_btc = State()
    available_coins = State()  # Will be represented in storage as 'Form:available_coins'
    coins = State()  # Will be represented in storage as 'Form:coins'


def get_open_trades2(user, chat_id):
    saves = r.scan_iter("At_" + chat_id + "_*_" + user)
    if saves is None:
        return 0
    else:
        c = 0
        for s in saves:
            c = c + 1
        return c

def get_symbol_list2(symbols):
    if "," in symbols:
        symbol_split = symbols.split(",")
    elif " " in symbols:
        symbol_split = symbols.split()
    else:
        symbol_split = [symbols]
    return symbol_split

@dp.message_handler(commands=['clearbags'])
async def reset_bags(message: types.Message):
    try:
        user = str(message.from_user.id)
        link = "At_" + str(message.chat.id) + "_*_*"
        saves = r.scan_iter(link)
        for key in saves:
            key = key.decode('utf-8')
            r.delete(key)
        await message.reply(f'Ok emptied all bags, enjoy. Reset funds with /gimme')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Failed to reset score. Contact... meh')

@dp.message_handler(commands=['gimme'])
async def add_bag_usd(message: types.Message):
    try:
        saves = r.scan_iter(SCORE_KEY.format(chat_id=str(message.chat.id), user_id="*"))   
        for key in saves:
            key = key.decode('utf-8')
            js = {"live": 0, "usd": 1000}
            r.set(key, json.dumps(js))
        await message.reply(f'Sup. You get a car, you get a car... everyone gets a lambo.')
    except Exception as e:
        logging.error("Gimme failed:" + str(e))
        await message.reply(f'{message.from_user.first_name} Failed to reset score. Contact... meh')

def get_user_bag_score(chat_id, user_id):
    try:
        key =  SCORE_KEY.format(chat_id=str(chat_id), user_id=user_id)
        js = r.get(key)
        if js is not None:
            js = js.decode('utf-8')
            js = json.loads(js)
            return float(js["live"]), float(js["usd"])
        else:
            js = {"live": 0, "usd": 1000}
            r.set(key, json.dumps(js))
            return 0, 1000
    except Exception as e:
        logging.error("FAILED to save user score for bag:" + str(e))

def user_spent_usd(chat_id, user_id, usd):
    try:
        _, account_usd = get_user_bag_score(chat_id, user_id)
        if account_usd is None:
            account_usd = 0
        new_account_usd = account_usd - usd
        if new_account_usd < 0:
            return None
        new_account_usd = round(new_account_usd, 2)    
        key =  SCORE_KEY.format(chat_id=str(chat_id), user_id=user_id)
        js = {"live": 0, "usd": new_account_usd}
        r.set(key, json.dumps(js))
        return new_account_usd
    except Exception as e:
        logging.error("FAILED to save user score for bag:" + str(e))
        return None

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['bag([\sa-zA-Z]*)']))
async def send_user_balance(message: types.Message, regexp_command):
    try:
        if regexp_command is not None:
            bysymbol = regexp_command.group(1)
        else: 
            bysymbol = None
        chat_id = str(message.chat.id)
        saves = r.scan_iter("At_" + chat_id + "_*_" + str(message.from_user.id))
        out = ""
        in_prices = get_user_price_config(message.from_user.id)
        out = out + "<pre>Buy At   |  +/-   | Coins  | $Value\n"
        total_change = float(0.00)
        counter = 0
        total_value = 0
        for key in saves:
            symbol = key.decode('utf-8').replace("At_" + chat_id + "_" , "").replace("_" + str(message.from_user.id),"")
            p, c, c24, btc_price = get_price(symbol)
            if float(p) > 0:
                value = r.get(key)
                if value is not None:
                    value = value.decode('utf-8')
                    if "{" in value:
                        js = json.loads(value)
                        usd_price = float(js["usd"])
                        buy_btc_price = float(js["btc"])
                        coins = float(js["coins"])
                    else:
                        usd_price = float(value)
                        buy_btc_price = "UNKNOWN"
                        coins = "UNKNOWN"
                    
                    if symbol.lower() != "btc" and ((bysymbol is not None and "btc" in bysymbol.lower()) or in_prices == "btc"):
                        price = str(round(btc_price,8))
                        if buy_btc_price == "UNKNOWN" or buy_btc_price == 0:
                            buy_price = buy_btc_price.ljust(8,' ')
                            change = 0
                        else:
                            buy_price = str(round(buy_btc_price, 6)).ljust(8,' ')
                            change = round(100 * (btc_price - buy_btc_price) / buy_btc_price, 2)
                    else:
                        buy_price = str(round_sense(usd_price)).ljust(8,' ')
                        price = str(round_sense(p))
                        if usd_price == 0:
                            change = 0
                        else:
                            change = round(100 * (p - usd_price) / usd_price, 2)
                    total_change = total_change + change
                    counter = counter + 1
                    change = get_change_label(change).ljust(5,' ')
                    symbol = symbol.upper()
                    usd_value = coins * p
                    total_value = total_value + usd_value
                    coins = str(round_sense(coins)).ljust(6,' ')
                    out = out + f"{symbol} @ ${price}:\n{buy_price} | {change} | {coins} | {round(usd_value,2)}\n"
            else:
                out = out + f"| {symbol} | NA | NA | NA | NA\n"
        
        _, usd = get_user_bag_score(chat_id, str(message.from_user.id))
        out = out + "\n            UNUSED USD = " + str(round(usd,2))
        out = out + "\n       TOTAL USD VALUE = " + str(round(total_value + usd,2)) + "\n"
        total_change = round(total_change, 2)
        out = out + "</pre>\nSUMMED CHANGE = " + str(total_change) + "%"
        if counter > 0:
            out = out + "\nAVERAGE CHANGE = " + str(round(total_change/counter,2)) + "%"
       
        await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")
    except Exception as e:
        logging.warn("Couldnt get hodl data:" + str(e))

def get_users_live_value(chat_id, user_id):
    try:
        saves = r.scan_iter("At_" + chat_id + "_*_" + user_id)
        total_value = float(0.00)
        for key in saves:
            symbol = key.decode('utf-8').replace("At_" + chat_id + "_" , "").replace("_" + user_id,"")
            p, c, c24, btc_price = get_price(symbol)
            if float(p) > 0:
                value = r.get(key)
                if value is not None:
                    value = value.decode('utf-8')
                    if "{" in value:
                        js = json.loads(value)
                        coins = float(js["coins"])
                    else:
                        coins = 1
                    total_value = total_value + (coins * p)
        return total_value
    except Exception as e:
        logging.warn("Couldnt get live values data:" + str(e))
        return 0

@dp.message_handler(commands=['ladder'])
async def totals_user_scores2(message: types.Message):
    try:
        chat_id = str(message.chat.id)
        
        saves = r.scan_iter(SCORE_KEY.format(chat_id=chat_id, user_id="*"))
        out = "League Season Standings:\n\n"
        out = ["<pre>Who?          Live Value  | USD\n"]
        scores = []
        for key in saves:
            key = key.decode('utf-8')
            value = r.get(key)
            if "*" in key:
                r.delete(key)
            elif value is not None:
                value = value.decode('utf-8')
                user_id = key.replace(chat_id + "_bagscore_", "")
                user_member = await bot.get_chat_member(chat_id, user_id)
                user = user_member.user.mention.ljust(14, ' ')
                js = json.loads(value)
                score_live = get_users_live_value(chat_id, user_id)
                score_usd = float(js["usd"])
                score_total = score_live + score_usd
                if len(scores) > 1:
                    i = 0
                    while i < len(scores) and score_total < scores[i]:
                        i = i + 1
                    score_live = str(round(score_live,2)).ljust(10, ' ')
                    out.insert(i, f"{user} {score_live} {score_usd}")
                    scores.insert(i, score_total)
                else:
                    scores.append(score_total)
                    score_live = str(round(score_live,2)).ljust(10, ' ')
                    out.append(f"{user} {score_live} {score_usd}")
        out.append("</pre>")
        s = "\n".join(out)
        await bot.send_message(chat_id=chat_id, text=s, parse_mode='HTML')
    except Exception as e:
        logging.error("ERROR: " + str(e))
        await message.reply(f'{message.from_user.first_name} Failed to get scores. Contact... meh')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['grab ([0-9a-zA-Z]*)']))
async def grab_point(message: types.Message, regexp_command, state: FSMContext):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list2(symbols)
        
        out = ""
        if len(symbol_split) > 1:
            await bot.send_message(chat_id=message.chat.id, text='Only 1 coin allowed at the moment, using first value')
        if len(symbol_split) > 0:
            symbol = symbol_split[0]
            symbol = symbol.strip().lower()
            p, _, _, btc_price = get_price(symbol)
            js = {}
            js["usd"] = p
            js["btc"] = btc_price
            r.set("At_" + symbol + "_" + str(message.from_user.id), json.dumps(js))
            out = out + f"Gotit. {symbol} at ${round_sense(p)} or {round(btc_price,8)} BTC marked \n"
        
        if p == 0:
            return await message.reply(f"Hey {name}, {symbol} is at not returning a price from API. Please try again.")
        
        _, usd = get_user_bag_score(chat_id=str(message.chat.id), user_id=str(message.from_user.id))
        if usd <= 0:
            return await message.reply(f"You have no USD, you fool.")
        
        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        name = chat_member.user.mention
        await Form.spent.set()
        async with state.proxy() as proxy:  # proxy = FSMContextProxy(state); await proxy.load()
            proxy['price_usd'] = p
            proxy['price_btc'] = btc_price
            proxy['coin'] = symbol
            proxy['balance'] = usd
        force_reply = types.force_reply.ForceReply(selective=True)
        await message.reply(f"{name}: {symbol} @ ${round_sense(p)}. Balance = ${usd} available. Buy $? worth (all for all)?", reply_markup=force_reply)

    except Exception as e:
        logging.error("BUY ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /buy btc')


@dp.message_handler(lambda message: not message.text.replace(".", "", 1).isdigit() and message.text.lower() != "all", state=Form.spent)
async def process_spent_invalid(message: types.Message):
    """
    If age is invalid
    """
    force_reply = types.force_reply.ForceReply()
    return await message.reply("Total Spend has gotta be a number.\nTYPE A NUMBER ONLY! (digits only)", reply_markup=force_reply)

@dp.message_handler(lambda message: message.text.replace(".", "", 1).isdigit() or message.text.lower() == "all", state=Form.spent)
async def process_spend(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            if message.text.lower().strip() == "all":
                spend = float(data['balance'])
            else:
                spend = float(message.text)
            price = float(data['price_usd'])
            chat_id = str(message.chat.id)
            user_id = str(message.from_user.id)
            if spend <= 0 or price == 0:
                return await message.reply("Total Spend or price has gotta be a more than 0.\nHow old are you? (digits only)")

            remaining_balance = user_spent_usd(chat_id, user_id, spend)
            if remaining_balance is None:
                return await message.reply("Total Spend is more than Account Balance\nHow old are you? (digits only)")

            coins = spend/price
            
            js = {}
            js["usd"] = data['price_usd']
            js["btc"] = data['price_btc']
            js["coins"] = coins 
            
            r.set("At_" + chat_id + "_" + data['coin'] + "_" + user_id, json.dumps(js))
            markup = types.ReplyKeyboardRemove()
            # And send message
            await bot.send_message(
                message.chat.id,
                md.text(
                    md.text('User:', md.code(message.from_user.mention)),
                    md.text('Coin:', md.code(data['coin'].upper())),
                    md.text('Price USD:', md.text(data['price_usd'])),
                    md.text('Price BTC:', md.text(data['price_btc'])),
                    md.text('Total Spent USD:', md.text(message.text)),
                    md.text('Total Coins:', md.text(str(coins))),
                    md.text('Remaining Balance USD:', md.text(str(remaining_balance))),
                    sep='\n',
                ),
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN,
            )

        # Finish conversation
        await state.finish()
    except Exception as e:
        logging.error("BUY ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /grab btc')


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        logging.info('Cancelling state None')
        return

    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await message.reply('Cancelled.', reply_markup=types.ReplyKeyboardRemove())



@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['dump ([\s0-9.,a-zA-Z]*)']))
async def set_dump_point(message: types.Message, regexp_command, state: FSMContext):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list2(symbols)
        user_id = str(message.from_user.id)
        chat_id = str(message.chat.id)
        
        out = ""
        if len(symbol_split) > 1:
            await bot.send_message(chat_id=message.chat.id, text='Only 1 coin allowed at the moment, using first value')
        if len(symbol_split) > 0:
            symbol = symbol_split[0]
            symbol = symbol.strip().lower()
            sale_price_usd, _, _, sale_price_btc = get_price(symbol)
            if sale_price_usd == 0:
                await message.reply("Sorry the API did not return a price for " + symbol + " try again in a minute.")
            else:
                js = r.get("At_" + chat_id + "_" + symbol + "_" + user_id).decode('utf-8')
                if js is not None:
                    js = json.loads(js)
                    price_usd = js["usd"]
                    price_btc = js["btc"]
                    available_coins = js["coins"]
                else:
                    price_btc = 0
                    price_btc = 0
                    available_coins = 0
                chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
                name = chat_member.user.mention
                await SaleForm.coins.set()
                async with state.proxy() as proxy:  # proxy = FSMContextProxy(state); await proxy.load()
                    proxy['coin'] = symbol
                    proxy['price_usd'] = price_usd
                    proxy['price_btc'] = price_btc
                    proxy['sale_price_usd'] = sale_price_usd
                    proxy['sale_price_btc'] = sale_price_btc
                    proxy['available_coins'] = available_coins
                force_reply = types.force_reply.ForceReply(selective=True)
                await message.reply(f"{name}: {symbol} @ ${round_sense(sale_price_usd)}. Coins = {available_coins} available. Sell ? coins (all for all)?", reply_markup=force_reply)
        else:
            await bot.send_message(chat_id=message.chat.id, text='Missing coin in sale, try /dump grt for example.')
        # out = out + f'\nFINAL BALANCE: ${new_balance}'        
        # await message.reply(out)
    except Exception as e:
        logging.error("Sell Error:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /sell btc')



@dp.message_handler(lambda message: not message.text.replace(".", "", 1).isdigit() and message.text.lower() != "all", state=SaleForm.coins)
async def process_sell_invalid(message: types.Message):
    """
    If age is invalid
    """
    force_reply = types.force_reply.ForceReply()
    return await message.reply("Total Coins to sell has gotta be a number or empty.\n Sell how many coins (digits only)?", reply_markup=force_reply)

@dp.message_handler(lambda message: message.text.replace(".", "", 1).isdigit() or message.text.lower() == "all", state=SaleForm.coins)
async def process_sell(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            if message.text.lower().strip() == "all":
                coins = float(data['available_coins'])
            else:
                coins = float(message.text)
            symbol = data['coin']
            sale_price_usd = float(data['sale_price_usd'])
            available_coins = float(data['available_coins'])
            chat_id = str(message.chat.id)
            user_id = str(message.from_user.id)
            if coins <= 0 or available_coins == 0 or sale_price_usd == 0:
                return await message.reply("Total Coins, Available Coins and Price has gotta be a more than 0.\n Try again (digits only)")

            if available_coins < coins:
                return await message.reply("Total Coins is more than Available Coins\nTry again (digits only)")

            r.delete("At_" + chat_id + "_" + symbol + "_" + user_id)    
            sale_usd = coins * sale_price_usd
            new_balance = user_spent_usd(chat_id, user_id, -1 * sale_usd)
            remaining_balance = available_coins - coins
            if remaining_balance == 0:
                r.delete("At_" + chat_id + "_" + symbol + "_" + user_id) 
            markup = types.ReplyKeyboardRemove()
            # And send message
            await bot.send_message(
                message.chat.id,
                md.text(
                    md.text('User:', md.code(message.from_user.mention)),
                    md.text('Coin:', md.code(data['coin'].upper())),
                    md.text('Buy Price USD:', md.text(data['price_usd'])),
                    md.text('Buy Price BTC:', md.text(data['price_btc'])),
                    md.text('Sale Price USD:', md.text(data['sale_price_usd'])),
                    md.text('Sale Price BTC:', md.text(data['sale_price_btc'])),
                    md.text('Total Coins Sold:', md.text(str(coins))),
                    md.text('Remaining Coins:', md.text(str(remaining_balance))),
                    md.text('Total From Sale USD:', md.text(str(round(sale_usd, 2)))),
                    md.text('New Bag Balance USD:', md.text(str(new_balance))),
                    sep='\n',
                ),
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN,
            )

        # Finish conversation
        await state.finish()
    except Exception as e:
        logging.error("SALE PROCESS ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /grab btc')



@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['dumper ([\s0-9.,a-zA-Z]*)']))
async def set_dump_point(message: types.Message, regexp_command, state: FSMContext):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list2(symbols)
        user_id = str(message.from_user.id)
        chat_id = str(message.chat.id)
        
        out = ""
        if len(symbol_split) > 1:
            await bot.send_message(chat_id=message.chat.id, text='Only 1 coin allowed at the moment, using first value')
        if len(symbol_split) > 0:
            symbol = symbol_split[0]
            symbol = symbol.strip().lower()
            sale_price_usd, _, _, sale_price_btc = get_price(symbol)
            if sale_price_usd == 0:
                await message.reply("Sorry the API did not return a price for " + symbol + " try again in a minute.")
            else:
                js = r.get("At_" + chat_id + "_" + symbol + "_" + user_id).decode('utf-8')
                if js is not None:
                    js = json.loads(js)
                    price_usd = js["usd"]
                    price_btc = js["btc"]
                    available_coins = js["coins"]
                else:
                    price_btc = 0
                    price_btc = 0
                    available_coins = 0
                chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
                name = chat_member.user.mention
                await SaleFormPercentage.coins.set()
                async with state.proxy() as proxy:  # proxy = FSMContextProxy(state); await proxy.load()
                    proxy['coin'] = symbol
                    proxy['price_usd'] = price_usd
                    proxy['price_btc'] = price_btc
                    proxy['sale_price_usd'] = sale_price_usd
                    proxy['sale_price_btc'] = sale_price_btc
                    proxy['available_coins'] = available_coins
                
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
                markup.add("25%", "50%", "75%", "100%")
                markup.add("Cancel")

                await message.reply(f"{name}: {symbol} @ ${round_sense(sale_price_usd)}. \nEither enter coins = {available_coins}, or selected percentage.\n Sell how many coins?", reply_markup=markup)
        else:
            await bot.send_message(chat_id=message.chat.id, text='Missing coin in sale, try /dump grt for example.')
        # out = out + f'\nFINAL BALANCE: ${new_balance}'        
        # await message.reply(out)
    except Exception as e:
        logging.error("Sell Percentage Error:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /dumper btc')


@dp.message_handler(lambda message: not message.text.replace(".", "", 1).isdigit() or message.text not in ["25%", "50%", "75%", "100%", "Cancel"], state=SaleFormPercentage.coins)
async def process_percentage_coin_invalid(message: types.Message):
    """
    In this example gender has to be one of: Male, Female, Other.
    """
    return await message.reply("Bad number of coins. Choose your coins from the keyboard or enter amount.")

@dp.message_handler(state=SaleFormPercentage.coins)
async def process_sell_percentage(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            selected_percentage = str(message.text)
            if selected_percentage == "100%":
                coins = float(data['available_coins'])
            elif selected_percentage == "75%":
                coins = float(data['available_coins']) * 0.75
            elif selected_percentage == "50%":
                coins = float(data['available_coins']) * 0.5
            elif selected_percentage == "25%":
                coins = float(data['available_coins']) * 0.25
            elif selected_percentage.lower() == "cancel":
                await state.finish()
                return await message.reply("Cancelled.")
            else:
                coins = float(message.text)
            if coins <= 0:
                await state.finish()
                return await message.reply("Coin error, <= 0.")

            symbol = data['coin']
            sale_price_usd = float(data['sale_price_usd'])
            available_coins = float(data['available_coins'])
            chat_id = str(message.chat.id)
            user_id = str(message.from_user.id)
            if coins <= 0 or available_coins == 0 or sale_price_usd == 0:
                return await message.reply("Total Coins, Available Coins and Price has gotta be a more than 0.\n Try again (digits only)")

            if available_coins < coins:
                return await message.reply("Total Coins is more than Available Coins\nTry again (digits only)")

            sale_usd = coins * sale_price_usd
            new_balance = user_spent_usd(chat_id, user_id, -1 * sale_usd)
            remaining_balance = available_coins - coins
            if remaining_balance == 0:
                r.delete("At_" + chat_id + "_" + symbol + "_" + user_id) 
            markup = types.ReplyKeyboardRemove()
            # And send message
            await bot.send_message(
                message.chat.id,
                md.text(
                    md.text('User:', md.code(message.from_user.mention)),
                    md.text('Coin:', md.code(data['coin'].upper())),
                    md.text('Buy Price USD:', md.text(data['price_usd'])),
                    md.text('Buy Price BTC:', md.text(data['price_btc'])),
                    md.text('Sale Price USD:', md.text(data['sale_price_usd'])),
                    md.text('Sale Price BTC:', md.text(data['sale_price_btc'])),
                    md.text('Total Coins Sold:', md.text(str(coins))),
                    md.text('Remaining Coins:', md.text(str(remaining_balance))),
                    md.text('Total From Sale USD:', md.text(str(round(sale_usd, 2)))),
                    md.text('New Bag Balance USD:', md.text(str(new_balance))),
                    sep='\n',
                ),
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN,
            )

        # Finish conversation
        await state.finish()
    except Exception as e:
        logging.error("SALE PROCESS ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /grab btc')
