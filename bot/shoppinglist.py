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

@dp.message_handler(commands=['pickup'])
async def pickup_list(message: types.Message):
    chat_id = message.chat.id
    mains = [""]
    try:
        config = json.loads(r.get(message.chat.id))
        logging.info(json.dumps(config))
        if "shop_list" in config:
            mains = config["shop_list"]
    except Exception as ex:
        logging.info("no config found, ignore")
    
    out = f"<pre>       Pickup\n"
    totes = 0

    
    for l in mains:
        l = l.ljust(25, ' ')
        out = out + f"{l} \n"
    out = out + "</pre>"
    await bot.send_message(chat_id=chat_id, text=out, parse_mode="HTML")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['+([\s0-9,.a-zA-Z]*)']))
async def add_to_shop(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1).strip()
        logging.info("config")
        config = r.get(message.chat.id)
        if config is None:
            config = {}
        else:
            config = json.loads(config)
        logging.info(json.dumps(config))
           
        if "shop_list" not in config:
            config["shop_list"] = []

        new_coin = new_coin.lower()
        if new_coin in config["shop_list"]:
            await message.reply(f'{message.from_user.first_name} Fail. Already Picked This One. ' + str(config["shop_list"]))
        else:
            config["shop_list"].append(new_coin)
            r.set(message.chat.id, json.dumps(config))
            await message.reply(f'Gotit. Added ' + new_coin)
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')



@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['-([\s0-9,.a-zA-Z]*)']))
async def remove_from_shop(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1).strip().lower()
        logging.info("config")
        config = r.get(message.chat.id)
        if config is not None:
            config = json.loads(config)
            if "shop_list" in config:
                if new_coin in config["shop_list"]:
                    config["shop_list"].remove(new_coin)
                    
                r.delete(message.chat.id, json.dumps(config))
                await message.reply(f'{message.from_user.first_name}, done. You bought ' + str(new_coin))
                return
                
        await message.reply(f'{message.from_user.first_name} Fail. Not found. ' + str(new_coin))
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')

