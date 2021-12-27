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
from .prices import get_bn_price, get_ohcl_trades, get_ath_ranks, get_change_label
from .user import get_user_price_config


@dp.message_handler(commands=['alts', 'ath', 'aths'])
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

    out = [f"<pre>{in_prices}    1hr   24hr  ATH-days   ATH%"]
    change_list = [""]

    data = get_ath_ranks(mains)
    if data is None:
        return await bot.send_message(chat_id=chat_id, text="Empty Data", parse_mode="HTML")

    for (l, d) in data.items():
        l = l.ljust(5, ' ')
        c_value = 0
        c_1 = ""
        c_24 = ""
        days_since = "0".ljust(5, ' ')
        ath_down = 0
        if in_prices == "USD":
            if "change_usd_1hr" in d:
                c_value = d["change_usd_1hr"]
                c_1 = get_change_label(c_value, 4)
            if "change_usd_24hr" in d:
                c_24 = get_change_label(d["change_usd_24hr"], 4)
        else:
            if "change_btc_1hr" in d:
                c_value = d["change_btc_1hr"]
                c_1 = get_change_label(c_value, 4)
            if "change_usd_24hr" in d:
                c_24 = get_change_label(d["change_usd_24hr"], 4)
        if "days_since_ath" in d:
            days_since = str(d["days_since_ath"]).ljust(5, ' ')
        if "down_from_alt" in d:
            ath_down = d["down_from_alt"]
        s = f"{l} {c_1} {c_24}  {days_since} {round(ath_down,1)}%"
        out.append(s)

    if len(out) > 50:
        await bot.send_message(chat_id=chat_id, text="\n".join(out[:50]) + "</pre>", parse_mode="HTML")
        out2 = [f"<pre>{in_prices}    1hr   24hr  ATH-days   ATH%"]
        out2.extend(out[50:])
        await bot.send_message(chat_id=chat_id, text="\n".join(out2) + "</pre>", parse_mode="HTML")
    else:
        await bot.send_message(chat_id=chat_id, text="\n".join(out) + "</pre>", parse_mode="HTML")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['watch ([a-zA-Z]*)']))
async def add_to_prices_alts(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1)
        config = r.get(message.chat.id)
        if config is None:
            config = {}
        else:
            config = json.loads(config)
        a = get_bn_price(new_coin)
        if "watch_list_alts" not in config:
            config["watch_list_alts"] = []
        if a == 0:
            arr = get_ohcl_trades(new_coin, 60)
            if arr is None:
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

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['remove ([a-zA-Z]*)']))
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
