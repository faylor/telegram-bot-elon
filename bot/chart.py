import logging
import json
import requests
import redis
import asyncio
import pandas as pd
import mplfinance as mpf
 
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
from .prices import get_last_trades, get_ohcl_trades

import pygal
from pygal.style import DarkStyle, DefaultStyle

@dp.message_handler(commands=['chart'])
async def chart(message: types.Message):
    chat_id = message.chat.id
    try:
        trades = get_last_trades(1000)
        points = []
        for t in trades:
            points.append(t[2])

        chart = pygal.StackedLine(fill=True, interpolate='cubic', style=DefaultStyle) # Setting style here is not necessary
        chart.add('BTC', points)
        chart.render_sparkline(width=500, height=25, show_dots=False)
        chart.render_to_png('chart.png')
        
        await bot.send_photo(chat_id=chat_id, photo=InputFile('chart.png'))
    except Exception as e:
        logging.error("ERROR Making chart:" + str(e))
        await bot.send_message(chat_id=chat_id, text="Failed to create chart", parse_mode="HTML")


@dp.message_handler(commands=['candle'])
async def chart(message: types.Message):
    chat_id = message.chat.id
    try:
        trades = get_ohcl_trades('btc')

        df = pd.DataFrame(data=trades, index_col=0, parse_dates=True)

        mpf.plot(df, type='candle', style='charles',
            title='S&P 500, Nov 2019',
            ylabel='Price ($)',
            ylabel_lower='Shares \nTraded',
            volume=True, 
            mav=(3,6,9), 
            savefig='test-mplfiance.png')
        
        await bot.send_photo(chat_id=chat_id, photo=InputFile('test-mplfiance.png'))
    except Exception as e:
        logging.error("ERROR Making chart:" + str(e))
        await bot.send_message(chat_id=chat_id, text="Failed to create chart", parse_mode="HTML")



