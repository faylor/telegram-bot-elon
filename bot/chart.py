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

@dp.message_handler(commands=['line'])
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

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['chart ([a-zA-Z]*)']))
async def candle(message: types.Message, regexp_command):
    chat_id = message.chat.id
    try:
        coin = regexp_command.group(1)
        trades = get_ohcl_trades(coin)
        trades = trades[60:]
        df = pd.DataFrame(trades, columns='time open high low close volume amount'.split())
        df['time'] = pd.DatetimeIndex(df['time']*10**9)
        df.set_index('time', inplace=True)

        mpf.plot(df, type='candle', style='yahoo',
            title=coin.upper() + " vs USDT",
            ylabel='Price ($)',
            ylabel_lower='Vol',
            volume=True, 
            mav=(3,6,9),
            figscale=3.0,
            savefig=coin + '-mplfiance.png')
        
        await bot.send_photo(chat_id=chat_id, photo=InputFile(coin + '-mplfiance.png'))
    except Exception as e:
        logging.error("ERROR Making chart:" + str(e))
        await bot.send_message(chat_id=chat_id, text="Failed to create chart", parse_mode="HTML")



