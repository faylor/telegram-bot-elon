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
from .prices import get_price, coin_price, round_sense, get_change_label
from .user import get_user_price_config

@dp.message_handler(commands=['prices', 'watching', 'btc', 'lambo', 'whenlambo', 'lambos', 'whenlambos', 'price', '$', '£', '€'])
async def prices(message: types.Message):
    chat_id = message.chat.id
    mains = ["BTC", "ETH", "GRT", "LTC", "ADA", "AAVE", "DOGE", "ZIL"]
    try:
        config = json.loads(r.get(message.chat.id))
        logging.info(json.dumps(config))
        if "watch_list" in config:
            mains = config["watch_list"]
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

    for l in mains:
        if coins is None:
            p, c, c24, btc_price = get_price(l)
        else:
            p = coins["USD"]["price"]
            c = coins["USD"]["percent_change_1h"]
            c24 = coins["USD"]["percent_change_24h"]
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

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['watch ([a-zA-Z]*)']))
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
        a, _, _, _ = get_price(new_coin)
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



@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['remove ([a-zA-Z]*)']))
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

