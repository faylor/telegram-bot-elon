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
from .bot import bot, dp, r, get_change_label
from .prices import get_price, round_sense
from .user import get_user_price_config
from .bn_testorders import BnOrder
bn_order = BnOrder()

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['mock ([\s0-9.,a-zA-Z]*)']))
async def test_bn_order(message: types.Message, regexp_command):
    try:
        logging.error("CHAT:" + str(message.chat.id))
        all = regexp_command.group(1)
        symbols, price, amount = all.strip().split()
        bn_order.create_test_order(message.chat.id, symbols, price, amount)
        bn_order.get_wallet(message.chat.id)
    except Exception as e:
        logging.error("START UP ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Start Stream")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['limitbuy ([\s0-9.,a-zA-Z]*)']))
async def bn_order_start(message: types.Message, regexp_command):
    try:
        all = regexp_command.group(1)
        symbols, price, amount = all.strip().split()
        bn_order.create_order(message.chat.id, symbols, price, amount)
        bn_order.get_wallet(message.chat.id)
    except Exception as e:
        logging.error("START UP ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Start Stream")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['marketbuy ([\s0-9.,a-zA-Z]*)']))
async def bn_order_market_buy(message: types.Message, regexp_command):
    try:
        all = regexp_command.group(1)
        symbols, amount = all.strip().split()
        logging.error("HERE:" + symbols)
        bn_order.create_market_buy(message.chat.id, symbols, amount)
        bn_order.get_wallet(message.chat.id)
    except Exception as e:
        logging.error("MARKET BUY ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Market Buy" + str(e))

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['marketsell ([\s0-9.,a-zA-Z]*)']))
async def bn_order_market_sell(message: types.Message, regexp_command):
    try:
        all = regexp_command.group(1)
        splits = all.strip().split()
        if len(splits) > 2:
            bn_order.create_market_sell(message.chat.id, splits[0], splits[1], splits[2])
        else:
            bn_order.create_market_sell(message.chat.id, splits[0], splits[1])
        bn_order.get_wallet(message.chat.id)
    except Exception as e:
        logging.error("MARKET SELL ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Market Sell" + str(e))

@dp.message_handler(commands=['account'])
async def get_bn_balance(message: types.Message):
    try:
        bn_order.get_wallet(message.chat.id)
    except Exception as e:
        logging.error("Account ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Get Account")


@dp.message_handler(commands=['checkorders'])
async def check_open_orders(message: types.Message):
    try:
        bn_order.check_orders(message.chat.id)
    except Exception as e:
        logging.error("START UP ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Start Stream")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['checktrades ([0-9.,a-zA-Z]*)']))
async def bn_check_symbol_trades(message: types.Message, regexp_command):
    try:
        symbol = regexp_command.group(1)
        bn_order.get_symbol_trades(message.chat.id, symbol)
    except Exception as e:
        logging.error("START UP ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Start Stream")


@dp.message_handler(commands=['cancelorders'])
async def cancel_open_orders(message: types.Message):
    try:
        bn_order.cancel_open_orders(message.chat.id)
    except Exception as e:
        logging.error("START UP ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Start Stream")
