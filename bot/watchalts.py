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
from .bot import dp, bot, r
from .prices import get_price, coin_price, get_ath_ranks, get_change_label, get_price_extended
from .user import get_user_price_config

@dp.message_handler(commands=['alts'])
async def prices_alts(message: types.Message):
    chat_id = message.chat.id
    mains = ["ETH", "GRT", "LTC", "ADA", "NANO", "NEO", "AAVE", "DOGE", "ZIL"]
    try:
        config = json.loads(r.get(message.chat.id))
        logging.info(json.dumps(config))
        if "watch_list_alts" in config:
            mains = config["watch_list_alts"]
    except Exception as ex:
        logging.info("no config found, ignore")
    in_prices = get_user_price_config(message.from_user.mention).upper()

    out = [f"<pre>{in_prices}   1hr  24hr  ATH-days   ATH%"]
    change_list = [""]
    for l in mains:
        c, c24, c_btc, c_btc_24, days_since, ath_down = get_price_extended(l)
        l = l.ljust(5, ' ')
        
        if in_prices == "USD":
            c_value = c
            change = get_change_label(c, 4)
            change24 = get_change_label(c24, 4)
        else:
            c_value = c_btc
            change = get_change_label(c_btc, 4)
            change24 = get_change_label(c_btc_24, 4)
        days_since = str(days_since).ljust(5, ' ')
        s = f"{l} {change} {change24}  {days_since} {round(ath_down,1)}%"
        if len(change_list) >= 2:
            i = 1
            while i < len(change_list) and c_value < change_list[i]:
                i = i + 1
            out.insert(i, s)
            change_list.insert(i,c_value)
        else:
            out.append(s)
            change_list.append(c_value)

    await bot.send_message(chat_id=chat_id, text="\n".join(out) + "</pre>", parse_mode="HTML")


@dp.message_handler(commands=['ath'])
async def prices_alts(message: types.Message):
    chat_id = message.chat.id
    mains = ["eth", "grt", "ltc", "ada", "nano", "neo", "aave", "doge", "zil", "ada"]
    try:
        config = json.loads(r.get(message.chat.id))
        logging.info(json.dumps(config))
        if "watch_list_alts" in config:
            mains = config["watch_list_alts"]
    except Exception as ex:
        logging.info("no config found, ignore")
    in_prices = get_user_price_config(message.from_user.mention).upper()

    out = [f"<pre>{in_prices}   24hr  ATH-days   ATH%"]
    change_list = [""]

    data = get_ath_ranks(mains)
    if data is None:
        return await bot.send_message(chat_id=chat_id, text="Empty Data", parse_mode="HTML")

    for l in mains:
        print(l.upper())
        print(data)
        d = data[l.upper()]
        l = l.ljust(5, ' ')
        
        if in_prices == "USD":
            c_value = data["change_usd_24hr"]
            change = get_change_label(data["change_usd_24hr"], 4)
        else:
            c_value = data["change_btc_24hr"]
            change = get_change_label(c_value, 4)
        days_since = str(data["days_since_ath"]).ljust(5, ' ')
        ath_down = data["down_from_alt"]
        s = f"{l} {change}  {days_since} {round(ath_down,1)}%"
        if len(change_list) >= 2:
            i = 1
            while i < len(change_list) and c_value < change_list[i]:
                i = i + 1
            out.insert(i, s)
            change_list.insert(i,c_value)
        else:
            out.append(s)
            change_list.append(c_value)

    await bot.send_message(chat_id=chat_id, text="\n".join(out) + "</pre>", parse_mode="HTML")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['watchalt ([a-zA-Z]*)']))
async def add_to_prices_alts(message: types.Message, regexp_command):
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
        if "watch_list_alts" not in config:
            config["watch_list_alts"] = []
        if a == 0:
            await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Code Not Found. Try /watchalt aave')
        else:
            new_coin = new_coin.lower()
            if new_coin in config["watch_list_alts"]:
                await message.reply(f'{message.from_user.first_name} Fail. Already Watching This One. ' + str(config["watch_list_alts"]))
            else:
                config["watch_list_alts"].append(new_coin)
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'Gotit. Added ' + new_coin)
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['removealt ([a-zA-Z]*)']))
async def remove_from_prices_alts(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1)
        logging.info("config")
        config = r.get(message.chat.id)
        if config is not None:
            config = json.loads(config)
            if "watch_list_alts" in config:
                if new_coin in config["watch_list_alts"]:
                    config["watch_list_alts"].remove(new_coin)
                elif new_coin.lower() in config["watch_list_alts"]:
                    config["watch_list_alts"].remove(new_coin.lower())
                elif new_coin.upper() in config["watch_list_alts"]:
                    config["watch_list_alts"].remove(new_coin.upper())
                    
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'{message.from_user.first_name}, done. Removed ' + str(new_coin))
                return
                
        await message.reply(f'{message.from_user.first_name} Fail. Not found. ' + str(new_coin))
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')
