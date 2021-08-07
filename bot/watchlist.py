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
from .bot import dp, r, bot
from .prices import get_price, coin_price, get_simple_price_gecko, round_sense, round_sense_str, get_change_label, coin_price_realtime, get_bn_price
from .user import get_user_price_config
from .chart import fibs_chart_extended

async def send_price_of(message: types.Message, regexp_command):
    try:
        symbol = regexp_command.group(1).strip()
        # _, c, c24, _ = get_price(symbol)
        price_gecko, btc_price = get_simple_price_gecko(symbol)
        price_bn = get_bn_price(symbol)
        price_bn_btc = get_bn_price(symbol, "BTC")
        data = coin_price_realtime(symbol, "USDT,BTC")
        if data is not None:
            usd_data = data[symbol.upper()]["quote"]["USDT"]
            btc_data = data[symbol.upper()]["quote"]["BTC"]
            p = usd_data["price"]
            c = usd_data["percent_change_1h"]
            c24 = usd_data["percent_change_24h"]
            p_btc = btc_data["price"]
            c_btc = btc_data["percent_change_1h"]
            c24_btc = btc_data["percent_change_24h"]
        else:
            p = 0
            c = 0
            c24 = 0
            p_btc = 0
            c_btc = 0
            c24_btc = 0
        await bot.send_message(chat_id=message.chat.id, 
                                text=f"<pre>USDT\nBinance - {symbol}: ${round_sense_str(price_bn)}\nCoinMarketCap - {symbol}: ${round_sense_str(p)}\nGecko API - {symbol}: ${round_sense_str(price_gecko)}\nChange: {round(c,2)}% 1hr    {round(c24,2)}% 24hr</pre>", 
        parse_mode="HTML")
        await bot.send_message(chat_id=message.chat.id, 
                                text=f"<pre>BTC\nBinance - {symbol}: {round_sense_str(price_bn_btc)}BTC\nCoinMarketCap - {symbol}: {round_sense_str(p_btc)}BTC\nGecko API - {symbol}: {round_sense_str(btc_price)}BTC  \nChange: {round(c_btc,2)}% 1hr    {round(c24_btc,2)}% 24hr</pre>", 
        parse_mode="HTML")
        saved = r.get("At_" + symbol.lower() + "_" + message.from_user.mention)
        if saved is not None:
            saved = saved.decode('utf-8')
            if "{" in saved:
                js = json.loads(saved)
                saved = float(js["usd"])
                saved_btc = float(js["btc"])
            else:
                saved = float(saved)
                saved_btc = 0
            changes = round(100 * (p - saved) / saved, 2)
            await bot.send_message(chat_id=message.chat.id, text=f"<pre>You marked at ${saved} and {saved_btc}BTC, changed by {changes}%</pre>", parse_mode="HTML")
        await fibs_chart_extended(message, regexp_command)
    except Exception as e:
        logging.warn("Could convert saved point:" + str(e))


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['whenlambo([\s0-9a-zA-Z]*)', 'lambo([\s0-9a-zA-Z]*)', 'prices([\s0-9a-zA-Z]*)', '\$([\s0-9a-zA-Z]*)', '\£([\s0-9a-zA-Z]*)', '\€([\s0-9a-zA-Z]*)']))
async def sorted_prices(message: types.Message, regexp_command):
    try:
        order_by = regexp_command.group(1)
        order_by = order_by.lower().strip()
        if order_by is None or order_by == "":
            order_by = "price"
    except:
        order_by = "price"
    
    if "1" in order_by:
        order_by = "percent_change_1h"
    elif "24" in order_by:
        order_by = "percent_change_24h"
    elif "price" not in order_by:
        return await send_price_of(message, regexp_command)
        
    chat_id = message.chat.id
    mains = ["BTC", "ETH", "GRT", "LTC", "ADA", "AAVE", "DOGE", "ZIL"]
    try:
        config = json.loads(r.get(message.chat.id))
        logging.info(json.dumps(config))
        if "watch_list_alts" in config:
            mains = config["watch_list_alts"]
    except Exception as ex:
        logging.info("no config found, ignore")
    in_prices = get_user_price_config(message.from_user.mention).upper()
    out = f"<pre>       {in_prices}    | 1hr      24hr\n"
    totes = 0

    try:
        coins = None
        coins = coin_price(mains)
    except:
        logging.error("FAILED TO GET COIN PRICES")

    ordered_coins = dict(sorted(coins.items(), key=lambda item: item[1]['quote']['USD'][order_by], reverse=True))

    for l in mains:
        if coins is None or l.upper() not in coins:
            p, c, c24, btc_price = get_price(l)
            tmp = {"quote": {"USD": {"price": p, "percent_change_1h": c, "percent_change_24h": c24}}}
            ordered_coins[l.upper()] = tmp

    for l, coin in ordered_coins.items():
        p = coin["quote"]["USD"]["price"]
        c = coin["quote"]["USD"]["percent_change_1h"]
        c24 = coin["quote"]["USD"]["percent_change_24h"]
        btc_price = 1
        totes = totes + c
        l = l.ljust(5, ' ')
        
        if in_prices == "USD":
            prices = str(round_sense(p))
        else:
            prices = str(round(btc_price,8))
        prices = prices.ljust(7, ' ')
        change = get_change_label(c)
        change24 = get_change_label(c24)
        out = out + f"{l} {prices} |{change}    {change24}\n"
    if totes < 0:
        out = out + "</pre>\n\n ☠️☠️☠️☠️☠️☠️" 
    elif totes > 6:
        out = out + "</pre>\n\n 🏎🏎🏎🏎🏎"
    else:
        out = out + "</pre>\n\n 🤷🏽🤷🏽🤷🏽🤷🏽🤷🏽"
    await bot.send_message(chat_id=chat_id, text=out, parse_mode="HTML")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['watchdeprecated ([a-zA-Z]*)']))
async def add_to_prices(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1)
        logging.info("config")
        config = r.get(message.chat.id)
        if config is None:
            config = {}
        else:
            config = json.loads(config)
        logging.info(json.dumps(config))
        
        coins = coin_price(new_coin)
        if coins is None or new_coin.upper() not in coins:
            a, _, _, _ = get_price(new_coin)
        else:
            a = coins[new_coin.upper()]["quote"]["USD"]["price"]
            
        if "watch_list" not in config:
            config["watch_list"] = []
        if a == 0:
            await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Code Not Found. Try /watch aave')
        else:
            new_coin = new_coin.lower()
            if new_coin in config["watch_list"]:
                await message.reply(f'{message.from_user.first_name} Fail. Already Watching This One. ' + str(config["watch_list"]))
            else:
                config["watch_list"].append(new_coin)
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'Gotit. Added ' + new_coin)
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')



@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['removedeprecated ([a-zA-Z]*)']))
async def remove_from_prices(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1)
        logging.info("config")
        config = r.get(message.chat.id)
        if config is not None:
            config = json.loads(config)
            if "watch_list" in config:
                if new_coin in config["watch_list"]:
                    config["watch_list"].remove(new_coin)
                elif new_coin.lower() in config["watch_list"]:
                    config["watch_list"].remove(new_coin.lower())
                elif new_coin.upper() in config["watch_list"]:
                    config["watch_list"].remove(new_coin.upper())
                    
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'{message.from_user.first_name}, done. Removed ' + str(new_coin))
                return
                
        await message.reply(f'{message.from_user.first_name} Fail. Not found. ' + str(new_coin))
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')

