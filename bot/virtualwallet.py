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

@dp.message_handler(commands=['newbaggies'])
async def new_bag_reset(message: types.Message):
    try:
        user = str(message.from_user.id)
        saves = r.scan_iter(SCORE_KEY.format(chat_id=str(message.chat.id), user_id="*"))
        for key in saves:
            key = key.decode('utf-8')
            js = {"live": 0, "usd": 1000}
            r.set(key, json.dumps(js))
        await message.reply(f'Sup. Welcome to a NEW season for trade scores for this chat.')
    except Exception as e:
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
        out = "HODLing:\n"
        in_prices = get_user_price_config(message.from_user.id)
        out = out + "<pre>       Buy At   |  Price   |  +/-  | Coins\n"
        total_change = float(0.00)
        counter = 0
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
                        price = str(round(btc_price,8)).ljust(10,' ')
                        if buy_btc_price == "UNKNOWN" or buy_btc_price == 0:
                            buy_price = buy_btc_price.ljust(8,' ')
                            change = 0
                        else:
                            buy_price = str(round(buy_btc_price, 6)).ljust(8,' ')
                            change = round(100 * (btc_price - buy_btc_price) / buy_btc_price, 2)
                    else:
                        buy_price = str(round_sense(usd_price)).ljust(8,' ')
                        price = str(round_sense(p)).ljust(8,' ')
                        if usd_price == 0:
                            change = 0
                        else:
                            change = round(100 * (p - usd_price) / usd_price, 2)
                    total_change = total_change + change
                    counter = counter + 1
                    change = get_change_label(change).ljust(5,' ')
                    symbol = symbol.ljust(4, ' ')
                    out = out + f"{symbol} | {buy_price} | {price} | {change} | {coins}\n"
            else:
                out = out + f"| {symbol} | NA | NA | NA | NA\n"
        total_change = round(total_change, 2)
        out = out + "</pre>\nSUMMED CHANGE = " + str(total_change) + "%"
        if counter > 0:
            out = out + "\nAVERAGE CHANGE = " + str(round(total_change/counter,2)) + "%"
        current_score = r.get(str(message.chat.id) + "_score2_" + str(message.from_user.id))
        if current_score is None:
            current_score = 0
        else:
            current_score = float(current_score.decode('utf-8'))
        out = out + "\nTOTAL SCORE = " + str(round(current_score,2)) + "\n"
        _, usd = get_user_bag_score(chat_id, str(message.from_user.id))
        out = out + "\nACCOUNT USD = " + str(round(usd,2)) + "\n"
        
        await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")
    except Exception as e:
        logging.warn("Couldnt get hodl data:" + str(e))

@dp.message_handler(commands=['league2'])
async def totals_user_scores2(message: types.Message):
    try:
        saves = r.scan_iter(SCORE_KEY.format(chat_id=str(message.chat.id), user_id="*"))
        out = "League Season Standings:\n\n"
        out = ["<pre>Who Dat?             Live Score  |  USD\n"]
        scores = []
        for key in saves:
            key = key.decode('utf-8')
            value = r.get(key)
            if "*" in key:
                r.delete(key)
            elif value is not None:
                value = value.decode('utf-8')
                user = key.replace(str(message.chat.id)+"_score2_", "")
                user = user.ljust(20, ' ')
                js = json.loads(value)
                score_live = round(float(js["live"]), 2)
                score_usd = round(float(js["usd"]), 2)
                score_total = score_live + score_usd
                if len(score_total) > 1:
                    i = 0
                    while i < len(score_total) and score_total < scores[i]:
                        i = i + 1
                    out.insert(i, f"{user} {score_live} {score_usd}")
                    
                    scores.insert(i, score_total)
                else:
                    scores.append(score_total)
                    out.append(f"{user} {score_live} {score_usd}")
        out.append("</pre>")
        s = "\n".join(out)
        await bot.send_message(chat_id=message.chat.id, text=s, parse_mode='HTML')
    except Exception as e:
        logging.error("ERROR: " + str(e))
        await message.reply(f'{message.from_user.first_name} Failed to get scores. Contact... meh')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['grab ([0-9a-zA-Z]*)']))
async def grab_point(message: types.Message, regexp_command, state: FSMContext):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list2(symbols)
        
        out = ""
        for symbol in symbol_split:
            symbol = symbol.strip().lower()
            p, _, _, btc_price = get_price(symbol)
            js = {}
            js["usd"] = p
            js["btc"] = btc_price
            r.set("At_" + symbol + "_" + str(message.from_user.id), json.dumps(js))
            out = out + f"Gotit. {symbol} at ${round_sense(p)} or {round(btc_price,8)} BTC marked \n"
        
        _, usd = get_user_bag_score(chat_id=str(message.chat.id), user_id=str(message.from_user.id))
        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        name = chat_member.user.mention
        if p == 0:
            return await message.reply(f"Hey {name}, {symbol} is at not returning a price from API. Please try again.")
        await Form.spent.set()
        async with state.proxy() as proxy:  # proxy = FSMContextProxy(state); await proxy.load()
            proxy['price_usd'] = p
            proxy['price_btc'] = btc_price
            proxy['coin'] = symbol
            proxy['balance'] = usd
        await message.reply(f"Hey {name},  {symbol} is at ${p}. You have ${usd} available so how much do you want to spend?")

    except Exception as e:
        logging.error("BUY ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /buy btc')


@dp.message_handler(lambda message: not message.text.isdigit(), state=Form.spent)
async def process_spent_invalid(message: types.Message):
    """
    If age is invalid
    """
    return await message.reply("Total Spend has gotta be a number.\nHow old are you? (digits only)")

@dp.message_handler(lambda message: message.text.isdigit(), state=Form.spent)
async def process_spend(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
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
            
            # Remove keyboard
            markup = types.ReplyKeyboardRemove()
            js = {}
            js["usd"] = data['price_usd']
            js["btc"] = data['price_btc']
            js["coins"] = coins 
            
            r.set("At_" + chat_id + "_" + data['coin'] + "_" + user_id, json.dumps(js))
            
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
        return

    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await message.reply('Cancelled.', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['buysplit2 ([\s0-9.,a-zA-Z]*)']))
async def set_buy_point2(message: types.Message, regexp_command):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list2(symbols)
        chat_id = str(message.chat.id)
        out = ""
        for symbol in symbol_split:
            symbol = symbol.strip().lower()
            p, _, _, btc_price = get_price(symbol)
            js = {}
            js["usd"] = p
            js["btc"] = btc_price
            r.set("At_" + chat_id + "_" + symbol + "_" + message.from_user.id, json.dumps(js))
            out = out + f"Gotit. {symbol} at ${round_sense(p)} or {round(btc_price,8)} BTC marked \n"
        
        await message.reply(out)
    except Exception as e:
        logging.error("BUY ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /buy btc')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['buyat2 ([\s0-9.,a-zA-Z]*)']))
async def set_buy_point_prices2(message: types.Message, regexp_command):
    try:
        coin_price = regexp_command.group(1)
        symbol_split = get_symbol_list2(coin_price)
        chat_id = str(message.chat.id)
        
        symbol = symbol_split[0]
        price = float(symbol_split[1])
        if symbol == "btc":
            price_btc = 1
        else:
            price_btc = float(symbol_split[2])
        
        symbol = symbol.strip().lower()

        js = {}
        js["usd"] = price
        js["btc"] = price_btc
        r.set("At_" + chat_id + "_" + symbol + "_" + message.from_user.id, json.dumps(js))
        out = f"Gotit. Hope this isnt a doge move. Gedit. {symbol} at ${round_sense(price)} or {round(price_btc,8)} BTC marked \n"
        
        await message.reply(out)
    except Exception as e:
        logging.error("BUY ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /buyat btc 23450 1')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['dump ([\s0-9.,a-zA-Z]*)']))
async def set_sell_point2(message: types.Message, regexp_command):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list2(symbols)
        user_id = str(message.from_user.id)
        chat_id = str(message.chat.id)
        
        out = ""
        for symbol in symbol_split:
            symbol = symbol.strip().lower()
            p, _, _, btc_price = get_price(symbol)
            if p == 0:
                await message.reply("Sorry the API did not return a price for " + symbol + " try again in a minute.")
            else:
                js = r.get("At_" + chat_id + "_" + symbol + "_" + user_id).decode('utf-8')
                changes = 0
                changes_btc = 0
                prop_changes = 0
                if js is not None:
                    if "{" in js:
                        js = json.loads(js)
                        saved = js["usd"]
                        saved_btc = js["btc"]
                        if saved_btc > 0:
                            changes_btc = round(100 * (btc_price - float(saved_btc)) / float(saved_btc), 2)
                        else:
                            changes_btc = "NA"
                    else:
                        saved = float(js)
                        saved_btc = 1
                        changes_btc = "<UNKNOWN>"
                    if saved > 0:
                        changes = round(100 * (p - float(saved)) / float(saved), 2)
                    out = out + f'Sold. {symbol} final diff in USD {changes}%  or in BTC {changes_btc} \n'

                trade_counts = get_open_trades2(user_id, chat_id)

                r.delete("At_" + chat_id + "_" + symbol + "_" + user_id)
                current_score = r.get(str(message.chat.id) + "_score_" + user_id)
                
                if current_score is None:
                    current_score = 0
                else:
                    current_score = float(current_score.decode('utf-8'))
                if changes == "NA":
                    new_score = current_score
                else:
                    if trade_counts > 0:
                        prop_changes = round(changes/trade_counts,2)
                    else:
                        prop_changes = changes
                    new_score = current_score + prop_changes
                new_score = str(round(new_score,2))
                out = out + f'Sold. {symbol} final diff in USD {changes}%  or in BTC {changes_btc} \n CHANGE PROFIT/LOSS = {changes}% \n OPEN TRADES = {trade_counts} \n TRADE SCORE = {prop_changes} \n  CURRENT SCORE = {new_score}'
                r.set(str(message.chat.id) + "_score2_" + user, new_score)
        await message.reply(out)
    except Exception as e:
        logging.error("Sell Error:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /sell btc')
