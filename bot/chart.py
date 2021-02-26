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
        trades = trades[-60:]
        df = pd.DataFrame(trades, columns='time open high low close volume amount'.split())
        df['time'] = pd.DatetimeIndex(df['time']*10**9)
        df.set_index('time', inplace=True)

        df['MA20'] = df['close'].rolling(window=20).mean()
        df['20dSTD'] = df['close'].rolling(window=20).std() 

        df['Upper'] = df['MA20'] + (df['20dSTD'] * 2)
        df['Lower'] = df['MA20'] - (df['20dSTD'] * 2)

        df = df.tail(35)

        apd  = [mpf.make_addplot(df['Lower'],color='#EC407A',width=0.9),
                mpf.make_addplot(df['Upper'],color='#42A5F5', width=0.9),
            mpf.make_addplot(df['MA20'],color='#FFEB3B',width=0.9)]

        kwargs = dict(type='candle',
            title=coin.upper() + " vs USDT",
            ylabel='Price ($)',
            ylabel_lower='Vol',volume=True,figratio=(3,2),figscale=2.1,addplot=apd)
        mpf.plot(df,**kwargs,style='nightclouds')
        mc = mpf.make_marketcolors(up='#00E676',down='#FF3D00',inherit=True)
        s  = mpf.make_mpf_style(base_mpf_style='nightclouds',facecolor='#121212',edgecolor="#131313",gridcolor="#232323",marketcolors=mc)
        mpf.plot(df,**kwargs, style=s, savefig=coin + '-mplfiance.png')
        
        await bot.send_photo(chat_id=chat_id, photo=InputFile(coin + '-mplfiance.png'))
    except Exception as e:
        logging.error("ERROR Making chart:" + str(e))
        await bot.send_message(chat_id=chat_id, text="Failed to create chart", parse_mode="HTML")



