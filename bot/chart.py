import logging
import json
import requests
import redis
import asyncio
import pandas as pd
import mplfinance as mpf
import numpy as np
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
        trades = get_last_trades(500)
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
async def candle(message: types.Message):
    chat_id = message.chat.id
    try:
        # trades = get_ohcl_trades('btc')
        arr = [[1614232980,41547.93,41572.28,41516.31,41532.75,1.062377,44130.68208997],[1614233040,41530.75,41532.75,41471.28,41474.81,0.74467,30908.75414289],[1614233100,41477.08,41537.03,41475.2,41500.39,0.864615,35878.76945827]]
        arr = np.array(arr)
        df = pd.DataFrame(arr, columns='time open high low close volume amount'.split())
        df['time'] = pd.DatetimeIndex(df['time']*10**9)

        logging.error("HERE")
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



