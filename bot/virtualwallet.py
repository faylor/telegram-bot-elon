import datetime
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
from .prices import get_price, get_simple_price_gecko, get_simple_prices_gecko, coin_price, round_sense, coin_price_realtime, get_bn_price
from .user import get_user_price_config, get_user_prizes

SCORE_KEY = "{chat_id}_bagscore_{user_id}"
SCORE_LOG_KEY = "{chat_id}_baglog_{user_id}"
PRICES_IN = "USDT"
MAX_TRADES = 60
# States
class Form(StatesGroup):
    coin = State()
    price_usd = State()
    price_btc = State()
    balance = State()
    spent = State()  # Will be represented in storage as 'Form:spent'

class SaleFormPercentage(StatesGroup):
    coin = State()
    price_usd = State()
    price_btc = State()
    sale_price_usd = State()
    sale_price_btc = State()
    available_coins = State()  # Will be represented in storage as 'Form:available_coins'
    coins = State()  # Will be represented in storage as 'Form:coins'

class POWCard(StatesGroup):
    user_id = State()
    chat_id = State()
    card = State()
    to_user = State()


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
        saves = r.scan_iter(SCORE_KEY.format(chat_id=str(message.chat.id), user_id="*"))
        for key in saves:
            key = key.decode('utf-8')
            js = {"live": 0, PRICES_IN.lower(): 0, "trades": 0}
            r.set(key, json.dumps(js))
        await message.reply(f'Ok emptied all bags, enjoy. Reset funds with /gimme')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Failed to reset score. Contact... meh')

@dp.message_handler(commands=['pow'])
async def use_card(message: types.Message, state: FSMContext):
    try:
        uid = str(message.from_user.id)
        chat_id = "-375104421"
        cards = get_user_prizes(uid, chat_id)
        if chat_id in cards:
            await POWCard.card.set()
            async with state.proxy() as proxy: 
                proxy['user_id'] = uid
                proxy['chat_id'] = chat_id
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
            for c in set(cards[chat_id]):
                markup.add(c)
            markup.add("Cancel")
            await message.reply(f"Use Which Card?", reply_markup=markup)
        else:
            await message.reply(f'No POW cards... Win some bets')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Failed to run POW Card. ' + str(e))


@dp.message_handler(state=POWCard.card)
async def use_card_specific(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            card_response = message.text.lower().strip()
            data['card'] = card_response
            if card_response == "red_shell":
                await POWCard.next()
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
                chat_id = str(message.chat.id)
                saves = r.scan_iter(SCORE_KEY.format(chat_id=chat_id, user_id="*"))
                for key in saves:
                    key = key.decode('utf-8')
                    value = r.get(key)
                    if value is not None:
                        value = value.decode('utf-8')
                        user_id = key.replace(chat_id + "_bagscore_", "")
                        user_member = await bot.get_chat_member(chat_id, user_id)
                        markup.add(user_member)
                await message.reply(f"To Whom Shall We Lock Out?", reply_markup=markup)
            elif card_response == "ghost":
                await POWCard.next()
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
                chat_id = str(message.chat.id)
                saves = r.scan_iter(SCORE_KEY.format(chat_id=chat_id, user_id="*"))
                for key in saves:
                    key = key.decode('utf-8')
                    value = r.get(key)
                    if value is not None:
                        value = value.decode('utf-8')
                        user_id = key.replace(chat_id + "_bagscore_", "")
                        user_member = await bot.get_chat_member(chat_id, user_id)
                        markup.add(user_member)
                await message.reply(f"To Whom Shall We Lock Out?", reply_markup=markup)
            elif card_response == "trade_token":
                # Add to users trade total
                print("not yet implemented")
                markup = types.ReplyKeyboardRemove()
            
                await message.reply(f"Added 2 Trades to your total!", reply_markup=markup)
                await state.finish()
    except Exception as e:
        print("use_card_specific: " + str(e))
       

@dp.message_handler(state=POWCard.to_user)
async def use_card_to_user(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            to_user = message.text
            markup = types.ReplyKeyboardRemove()
            card_response = data["card"]
            data["to_user"] = to_user
            await message.reply(f"Running {card_response} on {to_user}?", reply_markup=markup)
        await state.finish()
    except Exception as e:
        print("use_card_to_user: " + str(e))

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['gimme([\s0-9.]*)']))
async def add_bag_usd(message: types.Message, regexp_command):
    try:
        if regexp_command is not None:
            amount = float(regexp_command.group(1).strip())
        else: 
            amount = 10000
        saves = r.scan_iter(SCORE_KEY.format(chat_id=str(message.chat.id), user_id="*"))   
        for key in saves:
            key = key.decode('utf-8')
            saved = r.get(key)
            current_amount = 0
            if saved is not None:
                js = json.loads(saved.decode("utf-8"))
                if PRICES_IN.lower() in js:
                    current_amount = float(js[PRICES_IN.lower()])
            js = {"live": 0, PRICES_IN.lower(): amount + current_amount, "trades": 0}
            r.set(key, json.dumps(js))
        await message.reply(f'Sup. You get a car, you get a car... everyone gets a lambo.\n WELCOME TO Settlers of CRYPTAN\nTrade, Build & Settle as we build our empires together.\n')
    except Exception as e:
        logging.error("Gimme failed:" + str(e))
        await message.reply(f'{message.from_user.first_name} Failed to reset score. Contact... meh')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['bonus([\s0-9.]*)']))
async def add_bag_usd(message: types.Message, regexp_command):
    try:
        if regexp_command is not None:
            user_id = message.from_user.id
            amount = float(regexp_command.group(1).strip())
        else: 
            return await message.reply(f'Need the user and amount\n')
        key = SCORE_KEY.format(chat_id=str(message.chat.id), user_id=str(user_id))
        save = r.get(key) 
        current_amount = 0  
        if save is not None:
            js = json.loads(save.decode("utf-8"))
            if PRICES_IN.lower() in js:
                current_amount = float(js[PRICES_IN.lower()])
        js = {"live": 0, PRICES_IN.lower(): amount + current_amount, "trades": int(js["trades"])}
        r.set(key, json.dumps(js))

        await message.reply(f'Sup. You get a car, you get a car... everyone gets a lambo.\n WELCOME TO Settlers of CRYPTAN\nTrade, Build & Settle as we build our empires together.\n')
    except Exception as e:
        logging.error("Gimme failed:" + str(e))
        await message.reply(f'{message.from_user.first_name} Failed to reset score. Contact... meh')

@dp.message_handler(commands=['log'])
async def get_log(message: types.Message):
    try:
        log_key =  SCORE_LOG_KEY.format(chat_id=str(message.chat.id), user_id=str(message.from_user.id))
        current_log = r.get(log_key)
        if current_log is None:
            current_log = []
        else:
            current_log = json.loads(current_log.decode("utf-8"))
        out = ["Log (use clearlog to empty):"]
        for l in current_log:
            out.append(l["time"] + ": " + str(l["coin"]) + " sold for USD " + str(l["change"]))
        await message.reply('\n'.join(out))
    except Exception as e:
        logging.error("Log failed:" + str(e))
        await message.reply(f'{message.from_user.first_name} Failed to get log. Contact... meh')

@dp.message_handler(commands=['clearlog'])
async def get_log(message: types.Message):
    try:
        log_key =  SCORE_LOG_KEY.format(chat_id=str(message.chat.id), user_id=str(message.from_user.id))
        r.delete(log_key)
        await message.reply('CLEARED LOG.')
    except Exception as e:
        logging.error("Log failed:" + str(e))
        await message.reply(f'{message.from_user.first_name} Failed to get log. Contact... meh')


def get_user_bag_score(chat_id, user_id):
    try:
        key =  SCORE_KEY.format(chat_id=str(chat_id), user_id=user_id)
        js = r.get(key)
        if js is not None:
            js = js.decode('utf-8')
            js = json.loads(js)
            return float(js["live"]), float(js[PRICES_IN.lower()]), int(js["trades"])
        else:
            if PRICES_IN.lower() == "btc":
                amount = 1
            else:
                amount = 1000
            js = {"live": 0, PRICES_IN.lower(): amount, "trades": 0}
            r.set(key, json.dumps(js))
            return 0, amount, 0
    except Exception as e:
        logging.error("FAILED to save user score for bag:" + str(e))

def user_spent_usd(chat_id, user_id, usd, coin):
    try:
        _, account_usd, trade_count = get_user_bag_score(chat_id, user_id)
        if account_usd is None:
            account_usd = 0
        new_account_usd = account_usd - usd
        if new_account_usd < 0:
            return None
        new_account_usd = round(new_account_usd, 8)
        new_trades_count = trade_count + 1
        key =  SCORE_KEY.format(chat_id=str(chat_id), user_id=user_id)
        js = {"live": 0, PRICES_IN.lower(): new_account_usd, "trades": new_trades_count}
        r.set(key, json.dumps(js))
        log_key =  SCORE_LOG_KEY.format(chat_id=str(chat_id), user_id=user_id)
        current_log = r.get(log_key)
        if current_log is None:
            current_log = []
        else:
            current_log = json.loads(current_log.decode("utf-8"))
        current_log.append({"time": str(datetime.datetime.now()),"change": usd, "coin": coin, "balance":{"live": 0, PRICES_IN.lower(): new_account_usd}})
        r.set(log_key, json.dumps(current_log))
        return new_account_usd, new_trades_count
    except Exception as e:
        logging.error("FAILED to save user score for bag:" + str(e))
        return None



# @dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['stoploss([\sa-zA-Z]*)']))
# async def create_stop_loss(message: types.Message, regexp_command):
#     try:
#         string = regexp_command.group(1)
#         split_st = string.strip().split()
#         coin = split_st[0]
#         amount = float(split_st[0])
#         chat_id = str(message.chat.id)
#         user_id = message.from_user.id
#         saves = r.get("SL_" + coin.upper())
#         if saves is None:
#             saves = {amount: [{"c": chat_id, "u": user_id}]}
#         else:
#             saves = json.loads(saves.decode("utf-8"))
#             i = 0
#             for key in saves.keys():
#                 if saves[key] is not None:
#                     for s in saves[key]:
#                         if s["u"] == user_id and s["c"] == chat_id:
#                             saves[i] = 
#                 i = i + 1
                
#     except Exception as e:
#         logging.error("FAILED to create stop loss:" + str(e))
#         return None

# def trigger_stop_losses(price):
#     saves = r.get("SL_BTC")
#     if saves is not None:
#         saves = json.loads(saves.decode("utf-8"))
#         for key in saves.keys():

           
        

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['gobag([\sa-zA-Z]*)']))
async def send_user_balance_from_other_chat(message: types.Message, regexp_command):
    try:
        if regexp_command is not None:
            bysymbol = regexp_command.group(1)
        else: 
            bysymbol = None
        this_chat_id = str(message.chat.id)
        saves = r.scan_iter("At_*_" + str(message.from_user.id))
        out = ""
        # in_prices = get_user_price_config(message.from_user.id) GAME IS NOW SAME FOR ALL
        out = out + "<pre>Buy At   |  +/-   | Coins  | Val " + PRICES_IN + "\n"
        total_change = float(0.00)
        counter = 0
        total_value = 0
        last_the_chat_title = ""
        chat_id = None

        symbols = []
        keys = []
        chat_ids = []
        for key in saves:
            key = key.decode('utf-8')
            key_split = key.split("_")
            if "At_" + this_chat_id in key or len(key_split) < 4:
                # not this chats
                logging.info("Not a chat_id key:" + str(key))  
            else:
                chat_id = key_split[1]
                chat_ids.append(chat_id)
                symbols.append(key.replace("At_" + chat_id + "_" , "").replace("_" + str(message.from_user.id),""))
                keys.append(key)

        try:
            coin_prices = None
            coin_prices = coin_price_realtime(symbols, PRICES_IN)
        except:
            logging.error("FAILED TO GET COIN PRICES")
        i = 0
        for key in keys:
            symbol = symbols[i]
            if coin_prices is not None and symbol.upper() in coin_prices:
                p = coin_prices[symbol.upper()]["quote"][PRICES_IN]["price"]
            else:
                p = get_bn_price(symbol, PRICES_IN)  

            chat_id = chat_ids[i]
            if float(p) > 0:
                value = r.get(key)
                if value is not None:
                    value = value.decode('utf-8')
                    if "{" in value:
                        js = json.loads(value)
                        usd_price = float(js[PRICES_IN.lower()])
                        coins = float(js["coins"])
                    else:
                        usd_price = float(value)
                        coins = "UNKNOWN"
                    
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
                    the_chat = await bot.get_chat(chat_id)
                    the_chat_title = the_chat.title
                    if last_the_chat_title != the_chat_title:
                        out = out + f"{the_chat_title}\n"
                        last_the_chat_title = the_chat_title
                    out = out + f"{symbol} @ {price}{PRICES_IN}:\n{buy_price} | {change} | {coins} | {round_sense(usd_value)}\n"
            else:
                out = out + f"| {symbol} | NA | NA | NA | NA\n"
            i = i + 1
            
        if chat_id is not None:
            _, usd, trades = get_user_bag_score(chat_id, str(message.from_user.id))
            out = out + "\n             UNUSED " + PRICES_IN + " = " + str(round(usd,2))
            out = out + "\n        TOTAL " + PRICES_IN + " VALUE = " + str(round(total_value + usd,2)) + "\n"
            out = out + "\n        TRADE COUNT = " + str(trades) + " of MAX = " + str(MAX_TRADES) + "\n"
        else:
            out = out + "\n        TOTAL " + PRICES_IN + " VALUE = " + str(round(total_value,2)) + "\n"
        total_change = round(total_change, 2)
        out = out + "</pre>\n     SUMMED CHANGE = " + str(total_change) + "%"
        if counter > 0:
            out = out + "\n     AVERAGE CHANGE = " + str(round(total_change/counter,2)) + "%"
       
        await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")
    except Exception as e:
        logging.warn("Couldnt get hodl data:" + str(e))


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
        # in_prices = get_user_price_config(message.from_user.id)
        out = out + "<pre>Buy At   |  +/-   | Coins  | Val " + PRICES_IN + "\n"
        total_change = float(0.00)
        counter = 0
        total_value = 0

        symbols = []
        keys = []
        for key in saves:
            symbols.append(key.decode('utf-8').replace("At_" + chat_id + "_" , "").replace("_" + str(message.from_user.id),""))
            keys.append(key.decode('utf-8'))
        
        try:
            coin_prices = None
            coin_prices = coin_price_realtime(symbols, PRICES_IN)
        except:
            logging.error("FAILED TO GET COIN PRICES")
        i = 0
        for key in keys:
            symbol = symbols[i]
            if coin_prices is not None and symbol.upper() in coin_prices:
                p = coin_prices[symbol.upper()]["quote"][PRICES_IN]["price"]
                c = coin_prices[symbol.upper()]["quote"][PRICES_IN]["percent_change_1h"]
                c24 = coin_prices[symbol.upper()]["quote"][PRICES_IN]["percent_change_24h"]
            else:
                p = get_bn_price(symbol, PRICES_IN)                
            
            if float(p) > 0:
                value = r.get(key)
                if value is not None:
                    value = value.decode('utf-8')
                    if "{" in value:
                        js = json.loads(value)
                        usd_price = float(js[PRICES_IN.lower()])
                        coins = float(js["coins"])
                    else:
                        usd_price = float(value)
                        coins = "UNKNOWN"
                    
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
                    out = out + f"{symbol} @ {price}{PRICES_IN}:\n{buy_price} | {change} | {coins} | {round_sense(usd_value)}\n"
            else:
                out = out + f"| {symbol} | NA | NA | NA | NA\n"
            i = i + 1
        
        _, usd, trades = get_user_bag_score(chat_id, str(message.from_user.id))
        out = out + "\n             UNUSED " + PRICES_IN + " = " + str(round(usd,2))
        out = out + "\n        TOTAL " + PRICES_IN + " VALUE = " + str(round(total_value + usd,2)) + "\n"
        total_change = round(total_change, 2)
        out = out + "</pre>\n     SUMMED CHANGE = " + str(total_change) + "%"
        if counter > 0:
            out = out + "\n     AVERAGE CHANGE = " + str(round(total_change/counter,2)) + "%"
        out = out + "\n       TOTAL TRADES = " + str(trades) + " of MAX = " + str(MAX_TRADES) + "\n"
        
        if "022" in message.from_user.mention:
            out = '👑 Reigning Champ\n' + out
        await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")
    except Exception as e:
        logging.warn("Couldnt get hodl data:" + str(e))

def get_users_live_value(chat_id, user_id):
    try:
        saves = r.scan_iter("At_" + chat_id + "_*_" + user_id)

        symbols = []
        keys = []
        for key in saves:
            symbols.append(key.decode('utf-8').replace("At_" + chat_id + "_" , "").replace("_" + user_id,""))
            keys.append(key.decode('utf-8'))
        
        try:
            coin_prices = None
            coin_prices = coin_price_realtime(symbols, PRICES_IN)
        except:
            logging.error("FAILED TO GET COIN PRICES")

        total_value = float(0.00)
        i = 0
        for key in keys:
            symbol = symbols[i]

            if coin_prices is not None and symbol.upper() in coin_prices:
                p = coin_prices[symbol.upper()]["quote"][PRICES_IN]["price"]
            else:
                p = get_bn_price(symbol, PRICES_IN)
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
            i = i + 1
        return total_value
    except Exception as e:
        logging.warn("Couldnt get live values data:" + str(e))
        return 0

@dp.message_handler(commands=['ladder'])
async def totals_user_scores2(message: types.Message):
    try:
        chat_id = str(message.chat.id)
        
        saves = r.scan_iter(SCORE_KEY.format(chat_id=chat_id, user_id="*"))
        out = ["<pre>Who [Trades]           Live Val  " + PRICES_IN]
        scores = [0]
        for key in saves:
            key = key.decode('utf-8')
            value = r.get(key)
            if "*" in key:
                r.delete(key)
            elif value is not None:
                value = value.decode('utf-8')
                user_id = key.replace(chat_id + "_bagscore_", "")
                user_member = await bot.get_chat_member(chat_id, user_id)
                js = json.loads(value)
                score_live = get_users_live_value(chat_id, user_id)
                score_usd = float(js[PRICES_IN.lower()])
                score_usd_str = str(round_sense(score_usd)).ljust(8, ' ')
                trades_used = int(js["trades"])

                user = user_member.user.mention + "[" + str(trades_used) + "]"
                user = user.ljust(19, ' ')
                score_total = score_live + score_usd
                if len(scores) > 1:
                    i = 1
                    while i < len(scores) and score_total < scores[i]:
                        i = i + 1
                    score_live = str(round_sense(score_live)).ljust(10, ' ')
                    out.insert(i, f"🔸 {user} {score_live} {score_usd_str}")
                    scores.insert(i, score_total)
                else:
                    scores.append(score_total)
                    score_live = str(round_sense(score_live)).ljust(10, ' ')
                    out.append(f"🔸 {user} {score_live} {score_usd_str}")
        out.append("</pre>\nEnds Sunday 1st August, MAXIMUM TRADES (GRAB LOCKS) = " + str(MAX_TRADES))
        if len(out) > 3:
            out[1] =  out[1].replace('🔸', '👑')
            out[len(out)-2] = out[len(out)-2].replace('🔸', '🥄')
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
            p = get_bn_price(symbol, PRICES_IN) 
            if p == 0:
                return await message.reply(f"Hmmmm {symbol} is at not returning a price from API. Please try again.")
            _, usd, trades = get_user_bag_score(chat_id=str(message.chat.id), user_id=str(message.from_user.id))
            if usd <= 0:
                return await message.reply(f"You have no {PRICES_IN}, you fool.")
            if trades >= MAX_TRADES:
                return await message.reply(f"You have run out of TRADES! {MAX_TRADES}, you fool.")
            chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            name = chat_member.user.mention
            await Form.spent.set()
            async with state.proxy() as proxy:  # proxy = FSMContextProxy(state); await proxy.load()
                proxy['price_usd'] = p
                proxy['coin'] = symbol
                proxy['balance'] = usd
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
            markup.add("25%", "50%", "75%", "100%")
            markup.add("Manual Entry")
            markup.add("Cancel")

            await message.reply(f"{name}: {symbol} @ {round_sense(p)}{PRICES_IN}. \nBalance = {usd} {PRICES_IN} available. Buy?", reply_markup=markup)
        else:
            await message.reply(f"Add the Coin after grab, eg: /grab btc")
    except Exception as e:
        logging.error("BUY ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /buy btc')


@dp.message_handler(lambda message: message.text in ["Manual Entry"], state=Form.spent)
async def process_spent_invalid(message: types.Message):
    markup = types.ForceReply(force_reply=True, selective=True)
    return await message.reply("Enter Amount:", reply_markup=markup)

@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await message.reply('Cancelled.', reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(lambda message: not message.text.replace(".", "", 1).isdigit() and message.text not in ["25%", "50%", "75%", "100%", "Cancel", "cancel"], state=Form.spent)
async def process_spent_invalid(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add("25%", "50%", "75%", "100%")
    markup.add("Cancel")
    return await message.reply("Total Spend has gotta be a number.\nSelect percentage or write a number in box.", reply_markup=markup)

@dp.message_handler(commands=["cancel", "Cancel"])
async def cancel_main(message: types.Message):
    markup = types.ReplyKeyboardRemove()
    return await message.reply("Cancel All.", reply_markup=markup)

@dp.message_handler(commands=["cancel", "Cancel"])
async def cancel_spent(message: types.Message, state: FSMContext):
    await state.finish()
    markup = types.ReplyKeyboardRemove()
    return await message.reply("Cancelled.", reply_markup=markup)

@dp.message_handler(lambda message: message.text in ["cancel", "Cancel"], state=Form.spent)
async def cancel_spent(message: types.Message, state: FSMContext):
    await state.finish()
    markup = types.ReplyKeyboardRemove()
    return await message.reply("Cancelled.", reply_markup=markup)

@dp.message_handler(state=Form.spent)
async def process_spend(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            markup = types.ReplyKeyboardRemove()
            spent_response = message.text.lower().strip()
        
            if spent_response == "100%":
                spend = float(data['balance'])
            elif spent_response == "75%":
                spend = float(data['balance']) * 0.75
            elif spent_response == "50%":
                spend = float(data['balance']) * 0.50
            elif spent_response == "25%":
                spend = float(data['balance']) * 0.25
            elif spent_response == "cancel":
                await state.finish()
                return await message.reply("Cancelled.", reply_markup=markup)
            else:
                spend = float(message.text)
            if spend <= 0:
                await state.finish()
                return await message.reply("Coin error, <= 0.")

            price = float(data['price_usd'])
            if price == 0:
                 await state.finish()
                 return await message.reply("Prices look odd - please retry buy again.")

            chat_id = str(message.chat.id)
            user_id = str(message.from_user.id)
            if spend <= 0 or price == 0:
                return await message.reply("Total Spend or price has gotta be a more than 0.\nHow old are you? (digits only)")

            remaining_balance, trades_count = user_spent_usd(chat_id, user_id, spend, data['coin'])
            if remaining_balance is None:
                return await message.reply("Total Spend is more than Account Balance\nHow old are you? (digits only)")
                
            coins = spend/price
            
            js = r.get("At_" + chat_id + "_" + data['coin'] + "_" + user_id)
            if js is not None:
                js = json.loads(js.decode('utf-8'))
                current_coins = js["coins"]
                coins = coins + float(current_coins)

            js = {}
            js[PRICES_IN.lower()] = data['price_usd']
            js["coins"] = coins 
            
            r.set("At_" + chat_id + "_" + data['coin'] + "_" + user_id, json.dumps(js))
            # And send message
            await bot.send_message(
                message.chat.id,
                md.text(
                    md.text('User:', md.code(message.from_user.mention)),
                    md.text('Coin:', md.code(data['coin'].upper())),
                    md.text('Price ' + PRICES_IN + ':', md.text(round_sense(data['price_usd']))),
                    md.text('Total Spent ' + PRICES_IN + ':', md.text(message.text)),
                    md.text('Total Coins:', md.text(str(round(coins, 4)))),
                    md.text('Remaining Balance ' + PRICES_IN + ':', md.text(str(round_sense(remaining_balance)))),
                    md.text('Trades Used:', md.text(str(trades_count))),
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


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['panic([\s0-9.,a-zA-Z]*)']))
async def set_panic_point(message: types.Message, regexp_command):
    try:
        to_symbol = regexp_command.group(1)
    except:
        to_symbol = PRICES_IN.lower()
    try:
        if 'btc' in to_symbol.lower():
            return await bot.send_message(chat_id=message.chat.id, text='Sorry, BTC panic not yet implemented. Try /panic then buy BTC.')

        user_id = str(message.from_user.id)
        chat_id = str(message.chat.id)
        
        keys = r.scan_iter("At_" + chat_id + "_*_" + user_id)
        for key in keys:
            js = r.get(key).decode('utf-8')
            symbol = str(key.decode('utf-8')).replace(f"At_{chat_id}_","").replace(f"_{user_id}","")
            logging.error("COIN: " + symbol)
            sale_price_usd = get_bn_price(symbol, PRICES_IN)
            if sale_price_usd <= 0:
                return await bot.send_message(chat_id=message.chat.id, text='Sorry, the api returning 0 for this coin. Needs attention.')

            if js is not None:
                js = json.loads(js)
                price_usd = js[PRICES_IN.lower()]
                available_coins = js["coins"]
            else:
                return await bot.send_message(chat_id=message.chat.id, text='Sorry, the api didnt return for ' + key + ' so we have stopped panic sale.')

            sale_usd = available_coins * sale_price_usd
            new_balance, trades_count = user_spent_usd(chat_id, user_id, -1 * sale_usd, symbol)
            
            r.delete(key)
            profit_or_loss = (sale_price_usd * available_coins) - (price_usd * available_coins)
            if profit_or_loss > 0:
                profit_or_loss_md = md.text('Profit ' + PRICES_IN + ':', '🚀', md.text(str(round_sense(profit_or_loss))))
            else:
                profit_or_loss_md = md.text('Loss ' + PRICES_IN + ':', '🔻', md.text(str(round_sense(profit_or_loss))))
            # And send message
            await bot.send_message(
                message.chat.id,
                md.text(
                    md.text('User:', md.code(message.from_user.mention)),
                    md.text('Coin:', md.code(symbol.upper())),
                    md.text('Buy Price ' + PRICES_IN + ':', md.text(round_sense(price_usd))),
                    md.text('Sale Price ' + PRICES_IN + ':', md.text(round_sense(sale_price_usd))),
                    md.text('Total Coins Sold:', md.text(str(available_coins))),
                    md.text('Total From Sale ' + PRICES_IN + ':', md.text(str(round_sense(sale_usd)))),
                    profit_or_loss_md,
                    md.text('New Bag Balance ' + PRICES_IN + ':', md.text(str(new_balance))),
                    md.text('Trades Used:', md.text(str(trades_count))),
                    sep='\n',
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        await bot.send_message(chat_id=message.chat.id, text='Panic Fire Sale Done')
    except Exception as e:
        logging.error("Panic error: " + str(e))


@dp.message_handler(commands=['feelinglucky'])
async def set_panic_point(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        chat_id = str(message.chat.id)
        
        keys = r.scan_iter("At_" + chat_id + "_*_" + user_id)
        for key in keys:
            js = r.get(key).decode('utf-8')
            symbol = str(key.decode('utf-8')).replace(f"At_{chat_id}_","").replace(f"_{user_id}","")
            logging.error("COIN: " + symbol)
            sale_price_usd, _, _, sale_price_btc = get_price(symbol)
            data = coin_price_realtime(symbol)
            usd_data = data[symbol.upper()]["quote"][PRICES_IN]
            sale_price_usd = usd_data["price"]
            if js is not None:
                js = json.loads(js)
                price_usd = js[PRICES_IN.lower()]
                available_coins = js["coins"]
            else:
                return await bot.send_message(chat_id=message.chat.id, text='Sorry, the api didnt return for ' + key + ' so we have stopped panic sale.')

            sale_usd = available_coins * sale_price_usd
            new_balance, trades_count = user_spent_usd(chat_id, user_id, -1 * sale_usd, symbol)
            
            r.delete(key)
            profit_or_loss = (sale_price_usd * available_coins) - (price_usd * available_coins)
            if profit_or_loss > 0:
                profit_or_loss_md = md.text('Profit ' + PRICES_IN + ':', '🚀', md.text(str(round(profit_or_loss, 2))))
            else:
                profit_or_loss_md = md.text('Loss ' + PRICES_IN + ':', '🔻', md.text(str(round(profit_or_loss, 2))))
            # And send message
            await bot.send_message(
                message.chat.id,
                md.text(
                    md.text('User:', md.code(message.from_user.mention)),
                    md.text('Coin:', md.code(symbol.upper())),
                    md.text('Buy Price USD:', md.text(round_sense(price_usd))),
                    md.text('Sale Price USD:', md.text(round_sense(sale_price_usd))),
                    md.text('Sale Price BTC:', md.text(round(sale_price_btc, 6))),
                    md.text('Total Coins Sold:', md.text(str(available_coins))),
                    md.text('Total From Sale USD:', md.text(str(round(sale_usd, 2)))),
                    profit_or_loss_md,
                    md.text('New Bag Balance USD:', md.text(str(new_balance))),
                    md.text('Trades Used:', md.text(str(trades_count))),
                    sep='\n',
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        await bot.send_message(chat_id=message.chat.id, text='Panic Fire Sale Done')
    except Exception as e:
        logging.error("Panic error: " + str(e))


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
            sale_price_usd = get_bn_price(symbol, PRICES_IN) 
            if sale_price_usd == 0:
                await message.reply("Sorry the API did not return a price for " + symbol + " try again in a minute.")
            else:
                js = r.get("At_" + chat_id + "_" + symbol + "_" + user_id).decode('utf-8')
                if js is not None:
                    js = json.loads(js)
                    price_usd = js[PRICES_IN.lower()]
                    available_coins = js["coins"]
                else:
                    price_usd = 0
                    available_coins = 0
                chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
                name = chat_member.user.mention
                await SaleFormPercentage.coins.set()
                async with state.proxy() as proxy:  # proxy = FSMContextProxy(state); await proxy.load()
                    proxy['coin'] = symbol
                    proxy['price_usd'] = price_usd
                    proxy['sale_price_usd'] = sale_price_usd
                    proxy['available_coins'] = available_coins
                
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
                markup.add("25%", "50%", "75%", "100%")
                markup.add("Cancel")

                await message.reply(f"{name}: {symbol} @ {round_sense(sale_price_usd)}{PRICES_IN}. \nEither enter number of coins from availble {available_coins}, or selected percentage.\n Sell how many coins?", reply_markup=markup)
        else:
            await bot.send_message(chat_id=message.chat.id, text='Missing coin in sale, try /dump grt for example.')
        # out = out + f'\nFINAL BALANCE: ${new_balance}'        
        # await message.reply(out)
    except Exception as e:
        logging.error("Sell Percentage Error:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /dumper btc')


@dp.message_handler(lambda message: not message.text.replace(".", "", 1).isdigit() and message.text not in ["25%", "50%", "75%", "100%", "Cancel"], state=SaleFormPercentage.coins)
async def process_percentage_coin_invalid(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add("25%", "50%", "75%", "100%")
    markup.add("Cancel")

    return await message.reply("Bad number of coins. Choose your coins enter amount or percentage or cancel.", reply_markup=markup)

@dp.message_handler(state=SaleFormPercentage.coins)
async def process_sell_percentage(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            selected_percentage = str(message.text)
            markup = types.ReplyKeyboardRemove()
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
                return await message.reply("Cancelled.", reply_markup=markup)
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
            new_balance, trades_count = user_spent_usd(chat_id, user_id, -1 * sale_usd, symbol)
            remaining_balance = available_coins - coins
            if remaining_balance == 0:
                r.delete("At_" + chat_id + "_" + symbol + "_" + user_id)
            else:
                value = r.get("At_" + chat_id + "_" + symbol + "_" + user_id)
                if value is not None:
                    value = value.decode('utf-8')
                    js_set = json.loads(value)
                    js_set["coins"] = remaining_balance
                    r.set("At_" + chat_id + "_" + symbol + "_" + user_id, json.dumps(js_set))
                else:
                    return await message.reply("Total Coins For this coin is missing now...\nTry again (digits only)")
            
            profit_or_loss = (data["sale_price_usd"] * coins) - (data["price_usd"] * coins)
            if profit_or_loss > 0:
                profit_or_loss_md = md.text('Profit ' + PRICES_IN + ':', '🚀', md.text(str(round_sense(profit_or_loss))))
            else:
                profit_or_loss_md = md.text('Loss ' + PRICES_IN + ':', '🔻', md.text(str(round_sense(profit_or_loss))))
            # And send message
            await bot.send_message(
                message.chat.id,
                md.text(
                    md.text('User:', md.code(message.from_user.mention)),
                    md.text('Coin:', md.code(data['coin'].upper())),
                    md.text('Buy Price ' + PRICES_IN + ':', md.text(round_sense(data['price_usd']))),
                    md.text('Sale Price ' + PRICES_IN + ':', md.text(round_sense(data['sale_price_usd']))),
                    md.text('Total Coins Sold:', md.text(str(coins))),
                    md.text('Remaining Coins:', md.text(str(round(remaining_balance, 4)))),
                    md.text('Total From Sale ' + PRICES_IN + ':', md.text(str(round_sense(sale_usd)))),
                    profit_or_loss_md,
                    md.text('New Bag Balance ' + PRICES_IN + ':', md.text(str(new_balance))),
                    md.text('Trades Used:', md.text(str(trades_count))),
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
