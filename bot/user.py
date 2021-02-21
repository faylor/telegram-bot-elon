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
from .bot import r, dp

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['userprices ([a-zA-Z]*)']))
async def set_user_prices(message: types.Message, regexp_command):
    try:
        type = regexp_command.group(1)
        if type is None:
            await message.reply(f'{message.from_user.first_name} Fail. You Idiot. /userprices btc   or /userprices usd')
            return
        if type.lower() == "btc" or type.lower() == "usd":
            user = message.from_user.mention
            r.set("prices_" + user, type.lower())
            await message.reply(f'Gotit. Prices in {type} for {user}')
        else:
            await message.reply(f'{message.from_user.first_name} Fail. You Idiot. We only accept btc or usd prices. /userprices btc   or /userprices usd')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /bet btc 12.3k eth 1.2k')

def get_user_price_config(user):
    try:
        config = r.get("prices_" + user)
        if config is None:
            return "usd"
        else:
            return config.decode('UTF-8')
    except Exception as e:
        return "usd"

def add_win_for_user(config, user_id):
    if len(user_id.strip()) > 0:
        user_id = str(user_id)
        if user_id not in config["winners_list"]:
            config["winners_list"][user_id] = 1
        else:
            config["winners_list"][user_id] = int(config["winners_list"][user_id]) + 1
    