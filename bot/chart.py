import logging
import json
import requests
import redis
import asyncio
from aiogram import Bot, types
from aiogram.types.input_file import InputFile
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher, filters
from aiogram.utils.executor import start_webhook
from aiogram.dispatcher.webhook import SendMessage
from aiogram.utils.markdown import escape_md
from bot.settings import (TELEGRAM_BOT, HEROKU_APP_NAME,
                          WEBHOOK_URL, WEBHOOK_PATH,
                          WEBAPP_HOST, WEBAPP_PORT, REDIS_URL)
from .bot import dp, r, bot
from .prices import get_last_50_trades

import pygal
from pygal.style import LightSolarizedStyle

@dp.message_handler(commands=['chart'])
async def chart(message: types.Message):
    chat_id = message.chat.id
    try:
        trades = get_last_50_trades()
        points = []
        for t in trades:
            points.append(t[2])

        chart = pygal.Line(style=LightSolarizedStyle)
        chart.add('', points)
        chart.render_sparkline(width=500, height=25, show_dots=True)
        chart.render_to_png('chart.png')
        
        await bot.send_photo(chat_id=chat_id, photo=InputFile('chart.png'))
    except Exception as e:
        logging.error("ERROR Making chart:" + str(e))
        await bot.send_message(chat_id=chat_id, text="Failed to create chart", parse_mode="HTML")

