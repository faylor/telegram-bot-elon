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
from .bot import bot, dp, r, get_change_label
from .prices import get_price, round_sense
from .user import get_user_price_config

def get_open_trades(user):
    saves = r.scan_iter("At_*_" + user)
    if saves is None:
        return 0
    else:
        c = 0
        for s in saves:
            c = c + 1
        return c

def get_symbol_list(symbols):
    if "," in symbols:
        symbol_split = symbols.split(",")
    elif " " in symbols:
        symbol_split = symbols.split()
    else:
        symbol_split = [symbols]
    return symbol_split

@dp.message_handler(commands=['newseason'])
async def new_season_reset(message: types.Message):
    try:
        user = message.from_user.mention
        saves = r.scan_iter(str(message.chat.id) + "_score_*")
        for key in saves:
            key = key.decode('utf-8')
            r.set(key, 0)
        await message.reply(f'Sup. Welcome to a NEW season for trade scores for this chat.')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Failed to reset score. Contact... meh')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['hodl([\sa-zA-Z]*)']))
async def send_balance(message: types.Message, regexp_command):
    try:
        if regexp_command is not None:
            bysymbol = regexp_command.group(1)
        else: 
            bysymbol = None
        saves = r.scan_iter("At_*_" + message.from_user.mention)
        out = "HODLing:\n"
        in_prices = get_user_price_config(message.from_user.mention)
        out = out + "<pre>       Buy At   |  Price   |  +/-  \n"
        total_change = float(0.00)
        counter = 0
        for key in saves:
            symbol = key.decode('utf-8').replace("At_", "").replace("_" + message.from_user.mention,"")
            p, c, c24, btc_price = get_price(symbol)
            if float(p) > 0:
                value = r.get(key)
                if value is not None:
                    value = value.decode('utf-8')
                    if "{" in value:
                        js = json.loads(value)
                        usd_price = float(js["usd"])
                        buy_btc_price = float(js["btc"])
                    else:
                        usd_price = float(value)
                        buy_btc_price = "UNKNOWN"
                    
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
                    out = out + f"{symbol} | {buy_price} | {price} | {change}\n"
            else:
                out = out + f"| {symbol} | NA | NA | NA | \n"
        total_change = round(total_change, 2)
        out = out + "</pre>\nSUMMED CHANGE = " + str(total_change) + "%"
        if counter > 0:
            out = out + "\nAVERAGE CHANGE = " + str(round(total_change/counter,2)) + "%"
        current_score = r.get(str(message.chat.id) + "_score_" + message.from_user.mention)
        if current_score is None:
            current_score = 0
        else:
            current_score = float(current_score.decode('utf-8'))
        out = out + "\nTOTAL SCORE = " + str(round(current_score,2)) + "\n"
        await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")
    except Exception as e:
        logging.warn("Couldnt get hodl data:" + str(e))

@dp.message_handler(commands=['league'])
async def totals_user_scores(message: types.Message):
    try:
        saves = r.scan_iter(str(message.chat.id) + "_score_*")
        out = "League Season Standings:\n\n"
        out = ["<pre>Who Dat?             Score\n"]
        scores = []
        for key in saves:
            key = key.decode('utf-8')
            value = r.get(key)
            if "*" in key:
                r.delete(key)
            elif value is not None:
                value = value.decode('utf-8')
                user = key.replace(str(message.chat.id)+"_score_", "")
                user = user.ljust(20, ' ')
                score = round(float(value), 2)
                if len(scores) > 1:
                    i = 0
                    while i < len(scores) and score < scores[i]:
                        i = i + 1
                    out.insert(i, f"{user} {score}")
                    scores.insert(i, score)
                else:
                    scores.append(score)
                    out.append(f"{user} {score}")
        out.append("</pre>")
        s = "\n".join(out)
        await bot.send_message(chat_id=message.chat.id, text=s, parse_mode='HTML')
    except Exception as e:
        logging.error("ERROR: " + str(e))
        await message.reply(f'{message.from_user.first_name} Failed to get scores. Contact... meh')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['hodlbuy ([\s0-9.,a-zA-Z]*)']))
async def set_buy_point(message: types.Message, regexp_command):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list(symbols)
        
        out = ""
        for symbol in symbol_split:
            symbol = symbol.strip().lower()
            p, _, _, btc_price = get_price(symbol)
            js = {}
            js["usd"] = p
            js["btc"] = btc_price
            r.set("At_" + symbol + "_" + message.from_user.mention, json.dumps(js))
            out = out + f"Gotit. {symbol} at ${round_sense(p)} or {round(btc_price,8)} BTC marked \n"
        
        await message.reply(out)
    except Exception as e:
        logging.error("BUY ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /buy btc')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['hodlbuyat ([\s0-9.,a-zA-Z]*)']))
async def set_buy_point_prices(message: types.Message, regexp_command):
    try:
        coin_price = regexp_command.group(1)
        symbol_split = get_symbol_list(coin_price)
        
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
        r.set("At_" + symbol + "_" + message.from_user.mention, json.dumps(js))
        out = f"Gotit. Hope this isnt a doge move. Gedit. {symbol} at ${round_sense(price)} or {round(price_btc,8)} BTC marked \n"
        
        await message.reply(out)
    except Exception as e:
        logging.error("BUY ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /buyat btc 23450 1')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['^hodlsell ([\s0-9.,a-zA-Z]*)']))
async def set_sell_point(message: types.Message, regexp_command):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list(symbols)
        user = message.from_user.mention
        out = ""
        for symbol in symbol_split:
            symbol = symbol.strip().lower()
            p, _, _, btc_price = get_price(symbol)
            if p == 0:
                await message.reply(f"Sorry the API is not responding or the coin doesn't exist (remove with /deletecoins {symbols}).")
                return
            js = r.get("At_" + symbol + "_" + user).decode('utf-8')
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

            trade_counts = get_open_trades(user)

            r.delete("At_" + symbol + "_" + user)
            current_score = r.get(str(message.chat.id) + "_score_" + user)
            
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
            r.set(str(message.chat.id) + "_score_" + user, new_score)
        await message.reply(out)
    except Exception as e:
        logging.error("Sell Error:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /sell btc')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['hodldeletecoins ([\s0-9.,a-zA-Z]*)']))
async def delete_coin(message: types.Message, regexp_command):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list(symbols)
        user = message.from_user.mention
        for symbol in symbol_split:
            symbol = symbol.strip().lower()
            r.delete("At_" + symbol + "_" + user)
        await message.reply("Deleted coins.")
    except Exception as e:
        logging.error("Sell Error:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /sell btc')
