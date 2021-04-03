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
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from .bot import bot, dp, r, get_change_label
from .prices import get_price, round_sense
from .user import get_user_price_config
from .bn_testorders import BnOrder
bn_order = BnOrder()

class LimitForm(StatesGroup):
    coin = State()
    price_usd = State()
    price_btc = State()
    balance = State()
    spent = State()  # Will be represented in storage as 'Form:spent'

class MarketForm(StatesGroup):
    coin = State()
    buy_or_sell = State()
    purchase_with_coin = State()
    price_usd = State()
    price_btc = State()
    balance = State()
    spent = State()  # Will be represented in storage as 'Form:spent'


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


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['market ([\s0-9.,a-zA-Z]*)']))
async def bn_order_market_buy(message: types.Message, regexp_command, state: FSMContext):
    try:
        all = regexp_command.group(1)
        splits = all.strip().split()
        if len(splits) < 2:
            return await bot.send_message(chat_id=message.chat.id, text="Failed to Market Buy or Sell, no Coin given, eg: /market buy eth")
        buy_or_sell = splits[0].upper()
        if buy_or_sell not in ["BUY", "SELL"]:
            return await bot.send_message(chat_id=message.chat.id, text="Failed to Market Buy or Sell, must enter buy or sell first and then Coin given, eg: /market buy eth")
        coin = splits[1].upper()
        purchase_with_coin = "BTC"
        if len(splits) > 1:
            purchase_with_coin = splits[1].upper()
        
        sale_price_usd_tmp = bn_order.get_usd_price(coin)
        sale_price_btc_tmp = bn_order.get_btc_price(coin)
        
        purchase_coin_balance = bn_order.get_user_balance(purchase_with_coin)
        if purchase_coin_balance <= 0:
            return await message.reply(f"You have no balance in {purchase_with_coin}, you fool.")
        
        await MarketForm.spent.set()
        async with state.proxy() as proxy:  # proxy = FSMContextProxy(state); await proxy.load()
            proxy['price_usd'] = sale_price_usd_tmp
            proxy['price_btc'] = sale_price_btc_tmp
            proxy['coin'] = coin
            proxy['balance'] = purchase_coin_balance
            proxy['purchase_with_coin'] = purchase_with_coin
            proxy['buy_or_sell'] = buy_or_sell
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        markup.add("25%", "50%", "75%", "100%")
        markup.add("Cancel")
        name = message.from_user.mention
        await message.reply(f"{name}: {buy_or_sell} {coin} @ ~${round_sense(sale_price_usd_tmp)} and ~BTC{round_sense(sale_price_btc_tmp)}. \n{purchase_with_coin} Available Balance = {purchase_coin_balance} available. Use?", reply_markup=markup)

    except Exception as e:
        logging.error("bn order market buy - MARKET BUY OR SELL ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Market Buy" + str(e))


@dp.message_handler(lambda message: not message.text.replace(".", "", 1).isdigit() and message.text not in ["25%", "50%", "75%", "100%", "Cancel", "cancel"], state=MarketForm.spent)
async def process_spent_invalid(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add("25%", "50%", "75%", "100%")
    markup.add("Cancel")
    return await message.reply("Total Spend has gotta be a number.\nSelect percentage or write a number in box.", reply_markup=markup)


@dp.message_handler(lambda message: message.text in ["cancel", "Cancel"], state=MarketForm.spent)
async def cancel_spent(message: types.Message, state: FSMContext):
    markup = types.ReplyKeyboardRemove()
    await state.finish()
    return await message.reply("Cancelled.", reply_markup=markup)

@dp.message_handler(state=MarketForm.spent)
async def process_spend(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            markup = types.ReplyKeyboardRemove()
            spent_response = message.text.lower().strip()
        
            if spent_response == "100%":
                spend = float(data['balance'])
            elif spent_response == "75%":
                spend = float(data['balance']) * 0.75
            elif spent_response == "50%":
                spend = float(data['balance']) * 0.50
            elif spent_response == "25%":
                spend = float(data['balance']) * 0.25
            elif spent_response == "cancel":
                markup = types.ReplyKeyboardRemove()
                await state.finish()
                return await message.reply("Cancelled.", reply_markup=markup)
            else:
                spend = float(message.text)
            if spend <= 0:
                await state.finish()
                return await message.reply("Coin error, <= 0.")
            if data['buy_or_sell'] == "BUY":
                bn_order.create_market_buy(message.chat.id, data['coin'], spend, data['purchase_with_coin'])
            else:
                bn_order.create_market_sell(message.chat.id, data['coin'], spend, data['purchase_with_coin'])
            bn_order.get_wallet(message.chat.id)
            
        # Finish conversation
        await state.finish()
    except Exception as e:
        logging.error("Process Spend - MARKET BUY OR SELL ERROR:" + str(e))
        markup = types.ReplyKeyboardRemove()
        await message.reply(f'{message.from_user.first_name} Fail. Market Buy Or Sell Failed. /market buy btc... ' + str(e), reply_markup=markup)
        await state.finish()


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
