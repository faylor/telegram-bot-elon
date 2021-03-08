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
        trades = get_ohcl_trades(coin, 180)
        trades = trades[-60:]
        df = pd.DataFrame(trades, columns='time open high low close volume amount'.split())
        df['time'] = pd.DatetimeIndex(df['time']*10**9)
        df.set_index('time', inplace=True)

        df['MA20'] = df['close'].rolling(window=20).mean()
        df['20dSTD'] = df['close'].rolling(window=20).std() 

        df['Upper'] = df['MA20'] + (df['20dSTD'] * 2)
        df['Lower'] = df['MA20'] - (df['20dSTD'] * 2)

        rsi_df = get_rsi_df(df)
        df = df.tail(30)
        rsi_df = rsi_df.tail(30)

        apd  = [mpf.make_addplot(df['Lower'],color='#EC407A',width=0.9),
                mpf.make_addplot(df['Upper'],color='#42A5F5', width=0.9),
            mpf.make_addplot(df['MA20'],color='#FFEB3B',width=0.9)]

        if rsi_df is not None:
            apd.append(mpf.make_addplot(rsi_df, color='#FFFFFF', panel=1, ylabel='RSI', ylim=[0,100]))
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
        period_counts = 80

        if len(splits) > 1:
            period_seconds = splits[1]
            if period_seconds.lower() == "m" or period_seconds.lower() == "1m":
                period_seconds = 60
            elif period_seconds.lower() == "3m":
                period_seconds = 180
            elif period_seconds.lower() == "5m":
                period_seconds = 300
            elif period_seconds.lower() == "15m":
                period_seconds = 900
            elif period_seconds.lower() == "30m":
                period_seconds = 1800
            elif period_seconds.lower() == "60m" or period_seconds.lower() == "h" or period_seconds.lower() == "1h":
                period_seconds = 3600
            elif period_seconds.lower() == "2h":
                period_seconds = 7200
            elif period_seconds.lower() == "4h":
                period_seconds = 14400
            elif period_seconds.lower() == "6h":
                period_seconds = 21600
            elif period_seconds.lower() == "12h":
                period_seconds = 43200
            elif period_seconds.lower() == "24h" or period_seconds.lower() == "d" or period_seconds.lower() == "1d":
                period_seconds = 86400
            elif period_seconds.lower() == "3d":
                period_seconds = 259200
            elif period_seconds.lower() == "7d" or period_seconds.lower() == "w" or period_seconds.lower() == "1w":
                period_seconds = 604800
            elif period_seconds.isnumeric():
                period_seconds = int(period_seconds)
            else:
                return await bot.send_message(chat_id=chat_id, text="Failed to create chart, your period in seconds is not 1M, 3M, 5M, 15M, 30M, 1H, 2H, 4H, 6H, 12H, 1D, 3D, 1W of a number in seconds like 60, 180, 108000 etc")
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
        
        rsi_df = get_rsi_df(df)
        rsi_df = rsi_df.tail(int(period_counts))
        df = df.tail(int(period_counts))
        h_lines, y_min, y_max = fibs(df)

        apd  = [mpf.make_addplot(df['Lower'],color='#EC407A',width=0.9),
                mpf.make_addplot(df['Upper'],color='#42A5F5', width=0.9),
            mpf.make_addplot(df['MA20'],color='#FFEB3B',width=0.9)]
        
        if rsi_df is not None:
            apd.append(mpf.make_addplot(rsi_df, color='#FFFFFF', panel=1, ylabel='RSI', y_on_right=True, ylim=[0,100]))

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


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['fibex ([\s0-9.a-zA-Z]*)']))
async def fibs_chart_extended(message: types.Message, regexp_command):
    chat_id = message.chat.id
    try:
        inputs = regexp_command.group(1)
        splits = inputs.split()
        coin = splits[0]
        period_seconds = 60
        period_counts = 80

        if len(splits) > 1:
            period_seconds = splits[1]
            if period_seconds.lower() == "m" or period_seconds.lower() == "1m":
                period_seconds = 60
            elif period_seconds.lower() == "3m":
                period_seconds = 180
            elif period_seconds.lower() == "5m":
                period_seconds = 300
            elif period_seconds.lower() == "15m":
                period_seconds = 900
            elif period_seconds.lower() == "30m":
                period_seconds = 1800
            elif period_seconds.lower() == "60m" or period_seconds.lower() == "h" or period_seconds.lower() == "1h":
                period_seconds = 3600
            elif period_seconds.lower() == "2h":
                period_seconds = 7200
            elif period_seconds.lower() == "4h":
                period_seconds = 14400
            elif period_seconds.lower() == "6h":
                period_seconds = 21600
            elif period_seconds.lower() == "12h":
                period_seconds = 43200
            elif period_seconds.lower() == "24h" or period_seconds.lower() == "d" or period_seconds.lower() == "1d":
                period_seconds = 86400
            elif period_seconds.lower() == "3d":
                period_seconds = 259200
            elif period_seconds.lower() == "7d" or period_seconds.lower() == "w" or period_seconds.lower() == "1w":
                period_seconds = 604800
            elif period_seconds.isnumeric():
                period_seconds = int(period_seconds)
            else:
                return await bot.send_message(chat_id=chat_id, text="Failed to create chart, your period in seconds is not 1M, 3M, 5M, 15M, 30M, 1H, 2H, 4H, 6H, 12H, 1D, 3D, 1W of a number in seconds like 60, 180, 108000 etc")
        if len(splits) == 3:
            period_counts = splits[2]
            if period_counts.isnumeric():
                period_counts = int(period_counts)
            else:
                return await bot.send_message(chat_id=chat_id, text="Failed to create chart, your range is not a number, try 60 etc", parse_mode="HTML")
        logging.error("HERE1")
        trades = get_ohcl_trades(coin, period_seconds)
        logging.error("HERE2")
        
        ranger = -2 * period_counts
        trades = trades[ranger:]
        df = pd.DataFrame(trades, columns='time open high low close volume amount'.split())
        df['time'] = pd.DatetimeIndex(df['time']*10**9)
        df.set_index('time', inplace=True)

        logging.error("HERE3")
        
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['20dSTD'] = df['close'].rolling(window=20).std() 

        df['Upper'] = df['MA20'] + (df['20dSTD'] * 2)
        df['Lower'] = df['MA20'] - (df['20dSTD'] * 2)
        
        rsi_df = get_rsi_df(df)
        rsi_df = rsi_df.tail(int(period_counts))
        df = df.tail(int(period_counts))
        h_lines, y_min, y_max = fibs(df, extend=True)

        apd  = [mpf.make_addplot(df['Lower'],color='#EC407A',width=0.9),
                mpf.make_addplot(df['Upper'],color='#42A5F5', width=0.9),
                mpf.make_addplot(df['MA20'],color='#FFEB3B',width=0.9)]
        
        if rsi_df is not None:
            apd.append(mpf.make_addplot(rsi_df, color='#FFFFFF', panel=1, y_on_right=True, ylabel='RSI'))

        kwargs = dict(type='candle',ylabel=coin.upper() + ' Price in $',volume=True, volume_panel=1, figratio=(3,2),figscale=1.5,addplot=apd,ylim=[y_min,y_max])
        
        mpf.plot(df,**kwargs,style='nightclouds')
        mc = mpf.make_marketcolors(up='#69F0AE',down='#FF5252',inherit=True)
        s  = mpf.make_mpf_style(base_mpf_style='nightclouds',facecolor='#121212',edgecolor="#131313",gridcolor="#232323",marketcolors=mc)
        mpf.plot(df,**kwargs, style=s, scale_width_adjustment=dict(volume=0.55,candle=0.8), savefig=coin + '-mplfiance.png', hlines=h_lines)
        await bot.send_photo(chat_id=chat_id, photo=InputFile(coin + '-mplfiance.png'))
    except Exception as e:
        logging.error("ERROR Making chart:" + str(e))
        await bot.send_message(chat_id=chat_id, text="Failed to create chart", parse_mode="HTML")



def fibs(df, extend=False):

    fib = df['close']

    price_min = fib.min() #df.Close.min()
    price_max = fib.max() #df.Close.max()
    max_index = fib.idxmax()
    min_index = fib.idxmin()
    if max_index > min_index:
        logging.info("TRENDING UP")
        trend_direction = "UP"
    else:
        logging.info("TRENDING DOWN")
        trend_direction = "DOWN"

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
    
    fix = 26
    if extend == True:
        if trend_direction == "UP":
            thickness = thickness_top_line + thickness_second_line
            ydelta = 0.1 * (price_max+thickness-price_min)
            ymax= price_max + thickness + ydelta
            center_of_extend = price_max + thickness/2
            h_normal = [center_of_extend, center_of_top_line, center_of_second_line, center_of_third_line, center_of_forth_line]
            line_widths = [fix * thickness/ydelta, fix * thickness_top_line/ydelta, fix * thickness_second_line/ydelta, fix * thickness_third_line/ydelta, fix * thickness_forth_line/ydelta]
 
        else:
            thickness = thickness_forth_line + thickness_third_line
            ydelta = 0.1 * (price_max + thickness - price_min)
            center_of_extend = price_min - thickness/2
            price_min= price_min - thickness
            ymax= price_max + ydelta
            h_normal = [center_of_top_line, center_of_second_line, center_of_third_line, center_of_forth_line, center_of_extend]
            line_widths = [fix * thickness_top_line/ydelta, fix * thickness_second_line/ydelta, fix * thickness_third_line/ydelta, fix * thickness_forth_line/ydelta, fix * thickness/ydelta]
 
    else:
        ydelta = 0.1 * (price_max-price_min)
        ymax= price_max+ydelta
        h_normal = [center_of_top_line, center_of_second_line, center_of_third_line, center_of_forth_line]
        line_widths = [fix * thickness_top_line/ydelta, fix * thickness_second_line/ydelta, fix * thickness_third_line/ydelta, fix * thickness_forth_line/ydelta]
    
    if price_min > 0.0:
        setminy = max(0.9*price_min,price_min-ydelta)
    else:
        setminy = price_min-ydelta
    ymin = setminy
    h_lines = dict(hlines=h_normal,
                    colors=['#26C6DA', '#FEFEFE','#FFA726', '#EF5350', '#66BB6A'],
                    linewidths=line_widths,
                    alpha=0.15)

    return h_lines, ymin, ymax

def get_rsi_df(ticker):
    try:
        delta = ticker['close'].diff()
        up = delta.clip(lower=0)
        down = -1*delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up/ema_down
        ticker['RSI'] = 100 - (100/(1 + rs))
        return ticker["RSI"]    
    except Exception as e:
        logging.error("RSI failed:" + str(e))
        return None

