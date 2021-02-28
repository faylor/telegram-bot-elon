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

        df = df.tail(30)

        apd  = [mpf.make_addplot(df['Lower'],color='#EC407A',width=0.9),
                mpf.make_addplot(df['Upper'],color='#42A5F5', width=0.9),
            mpf.make_addplot(df['MA20'],color='#FFEB3B',width=0.9)]

        kwargs = dict(type='candle',ylabel=coin.upper() + ' Price in $',volume=True,figratio=(3,2),figscale=1.5,addplot=apd)
        mpf.plot(df,**kwargs,style='nightclouds')
        mc = mpf.make_marketcolors(up='#69F0AE',down='#FF5252',inherit=True)
        s  = mpf.make_mpf_style(base_mpf_style='nightclouds',facecolor='#121212',edgecolor="#131313",gridcolor="#232323",marketcolors=mc)
        mpf.plot(df,**kwargs, style=s,scale_width_adjustment=dict(volume=0.55,candle=0.8), savefig=coin + '-mplfiance.png')
        await bot.send_photo(chat_id=chat_id, photo=InputFile(coin + '-mplfiance.png'))
    except Exception as e:
        logging.error("ERROR Making chart:" + str(e))
        await bot.send_message(chat_id=chat_id, text="Failed to create chart", parse_mode="HTML")


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['fibs ([\s0-9.a-zA-Z]*)']))
async def fibs_chart(message: types.Message, regexp_command):
    chat_id = message.chat.id
    try:
        inputs = regexp_command.group(1)
        splits = inputs.split()
        coin = splits[0]
        period_seconds = 60
        period_counts = 60

        if len(splits) > 1:
            period_seconds = splits[1]
            if period_seconds.lower() == "1m":
                period_seconds = 60
            elif period_seconds.lower() == "3m":
                period_seconds = 180
            elif period_seconds.lower() == "1d":
                period_seconds = 108000
            elif period_seconds.isnumeric():
                period_seconds = int(period_seconds)
            else:
                return await bot.send_message(chat_id=chat_id, text="Failed to create chart, your period in seconds is not 1M, 3M, 1D of a number in seconds like 60, 180, 108000 etc")
        if len(splits) == 3:
            period_counts = splits[2]
            if period_counts.isnumeric():
                period_counts = int(period_counts)
            else:
                return await bot.send_message(chat_id=chat_id, text="Failed to create chart, your range is not a number, try 60 etc", parse_mode="HTML")
            
        trades = get_ohcl_trades(coin, period_seconds)
        ranger = -2 * period_counts
        trades = trades[ranger:]
        df = pd.DataFrame(trades, columns='time open high low close volume amount'.split())
        df['time'] = pd.DatetimeIndex(df['time']*10**9)
        df.set_index('time', inplace=True)

        df['MA20'] = df['close'].rolling(window=20).mean()
        df['20dSTD'] = df['close'].rolling(window=20).std() 

        df['Upper'] = df['MA20'] + (df['20dSTD'] * 2)
        df['Lower'] = df['MA20'] - (df['20dSTD'] * 2)
        df = df.tail(int(period_counts))
        h_lines, y_min, y_max = fibs(df)

        apd  = [mpf.make_addplot(df['Lower'],color='#EC407A',width=0.9),
                mpf.make_addplot(df['Upper'],color='#42A5F5', width=0.9),
            mpf.make_addplot(df['MA20'],color='#FFEB3B',width=0.9)]

        if y_min is None:
            kwargs = dict(type='candle',ylabel=coin.upper() + ' Price in $',volume=True,figratio=(3,2),figscale=1.5,addplot=apd)
        else:
            kwargs = dict(type='candle',ylabel=coin.upper() + ' Price in $',volume=True,figratio=(3,2),figscale=1.5,addplot=apd,ylim=[y_min,y_max])
        
        mpf.plot(df,**kwargs,style='nightclouds')
        mc = mpf.make_marketcolors(up='#69F0AE',down='#FF5252',inherit=True)
        s  = mpf.make_mpf_style(base_mpf_style='nightclouds',facecolor='#121212',edgecolor="#131313",gridcolor="#232323",marketcolors=mc)
        mpf.plot(df,**kwargs, style=s, scale_width_adjustment=dict(volume=0.55,candle=0.8), savefig=coin + '-mplfiance.png', hlines=h_lines)
        await bot.send_photo(chat_id=chat_id, photo=InputFile(coin + '-mplfiance.png'))
    except Exception as e:
        logging.error("ERROR Making chart:" + str(e))
        await bot.send_message(chat_id=chat_id, text="Failed to create chart", parse_mode="HTML")



def fibs(df):

    fib = df['close']

    price_min = fib.min() #df.Close.min()
    price_max = fib.max() #df.Close.max()
    difference = abs(price_max - price_min)
    h_lines = []
    thickness_top_line = (0.236 * (price_max - price_min))
    bottom_top_line = price_max - thickness_top_line
    center_of_top_line = price_max - thickness_top_line/2

    level2 = (0.382 * (price_max - price_min))
    bottom_second_line = price_max - level2
    thickness_second_line = abs(bottom_second_line - bottom_top_line)
    center_of_second_line = bottom_top_line - thickness_second_line/2

    level3 = (0.618 * (price_max - price_min))
    bottom_third_line = price_max - level3
    thickness_third_line = abs(bottom_third_line - bottom_second_line)
    center_of_third_line = bottom_second_line - thickness_third_line/2

    thickness_forth_line = abs(bottom_third_line - price_min)
    center_of_forth_line = bottom_third_line - thickness_forth_line/2
    
    ydelta = 0.1 * (price_max-price_min)
    if price_min > 0.0:
        # don't let it go negative:
        setminy = max(0.9*price_min,price_min-ydelta)
    else:
        setminy = price_min-ydelta
    ymin = setminy
    ymax= price_max+ydelta
    fix = 26
    h_lines = dict(hlines=[center_of_top_line, center_of_second_line, center_of_third_line, center_of_forth_line],
                    colors=['#26C6DA', '#66BB6A','#FFA726', '#EF5350'],
                    linewidths=[fix * thickness_top_line/ydelta, fix * thickness_second_line/ydelta, fix * thickness_third_line/ydelta, fix * thickness_forth_line/ydelta],
                    alpha=0.15)

    return h_lines, ymin, ymax