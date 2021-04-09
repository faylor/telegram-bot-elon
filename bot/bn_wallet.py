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
    buying_coin = State()
    selling_coin = State()
    exchange_symbol = State()
    buying_price_usd = State()
    buying_price_btc = State()
    selling_price_usd = State()
    selling_price_btc = State()
    oco = State()
    tsl = State()
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

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['limit ([\s0-9.,a-zA-Z]*)']))
async def bn_order_start(message: types.Message, regexp_command):
    try:
        all = regexp_command.group(1)
        buy_or_sell, first_coin, second_coin, price, amount = all.strip().upper().split()
        if buy_or_sell not in ["BUY", "SELL"]:
            return await bot.send_message(chat_id=message.chat.id, text="Failed to Market Buy or Sell, must enter buy or sell first and then Coin given, eg: /market buy eth")
        if buy_or_sell == "BUY":
            buying_coin = first_coin
            selling_coin = second_coin
        else:
            buying_coin = second_coin
            selling_coin = first_coin
        bn_order.create_order(message.chat.id, selling_coin, buying_coin, price, amount)
        bn_order.get_wallet(message.chat.id)
        
    except Exception as e:
        logging.error("START UP ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Start Stream")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['tsl ([\s0-9.,a-zA-Z]*)']))
async def bn_tsl_start(message: types.Message, regexp_command):
    try:
        all = regexp_command.group(1)
        buy_or_sell, first_coin, second_coin = all.strip().upper().split()
        if buy_or_sell not in ["BUY", "SELL"]:
            return await bot.send_message(chat_id=message.chat.id, text="Failed to Market Buy or Sell, must enter buy or sell first and then Coin given, eg: /market buy eth")
        if buy_or_sell == "SELL":
            buying_coin = first_coin
            selling_coin = second_coin
        else:
            buying_coin = second_coin
            selling_coin = first_coin
        bn_order.create_trailing_stop_limit(market=buying_coin.upper() + selling_coin.upper(), buy_coin=buying_coin, sell_coin=selling_coin, type=buy_or_sell.lower(), stop_percentage=0.0099, interval=10)
        
    except Exception as e:
        logging.error("START UP TSL ERROR:" + str(e))
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
        first_coin = splits[1].upper()
        second_coin = "BTC"
        oco = False
        tsl = False
        if len(splits) > 2:
            if "OCO" in splits[2].upper():
                oco = True
            elif "TSL" in splits[2].upper():
                tsl = True
            else:
                second_coin = splits[2].upper()
            if len(splits) > 3 and "OCO" in splits[3].upper():
                oco = True
            elif len(splits) > 3 and "TSL" in splits[3].upper():
                tsl = True
        if buy_or_sell == "BUY":
            buying_coin = first_coin
            selling_coin = second_coin
        else:
            buying_coin = second_coin
            selling_coin = first_coin
        
        purchase_coin_balance = bn_order.get_user_balance(selling_coin)
        selling_price_usd_tmp = bn_order.get_usd_price(selling_coin)
        selling_price_btc_tmp = bn_order.get_btc_price(selling_coin)
        buying_price_usd_tmp = bn_order.get_usd_price(buying_coin)
        buying_price_btc_tmp = bn_order.get_btc_price(buying_coin)
        if purchase_coin_balance <= 0:
            return await message.reply(f"You have no balance in {selling_coin}, you fool.")
        await MarketForm.spent.set()
        async with state.proxy() as proxy:  # proxy = FSMContextProxy(state); await proxy.load()
            proxy['selling_price_usd'] = selling_price_usd_tmp
            proxy['selling_price_btc'] = selling_price_btc_tmp
            proxy['buying_price_usd'] = buying_price_usd_tmp
            proxy['buying_price_btc'] = buying_price_btc_tmp
            proxy['buying_coin'] = buying_coin
            proxy['selling_coin'] = selling_coin
            proxy['balance'] = purchase_coin_balance
            proxy['buy_or_sell'] = buy_or_sell
            proxy['oco'] = oco
            proxy['tsl'] = tsl
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        markup.add("25%", "50%", "75%", "100%")
        markup.add("Cancel")
        name = message.from_user.mention
        oco_text = "OCO is set to "
        if oco:
            oco_text = oco_text + "ON. 3% Profit or 1% Loss will trigger a Swap Back to Original."
        else:
            oco_text = oco_text + "OFF. No stop limits or profit limits are raised. Use oco or tsl instead if required eg: /market buy bnb usdt oco"
        tsl_text = "Trailing Stop Limit (TSL) is set to "
        if tsl:
            tsl_text = tsl_text + "ON. Tailing 1% Loss will move up."
        else:
            tsl_text = tsl_text + "OFF. No stop limits raised. Use oco or tsl instead if required eg: /market buy bnb usdt oco"
        text = f"""{name}: BUY {buying_coin} @ ~${bn_order.round_sense(buying_price_usd_tmp)} and ~BTC {bn_order.round_sense(buying_price_btc_tmp)}
SELL {selling_coin} @ ~${bn_order.round_sense(selling_price_usd_tmp)} and ~BTC {bn_order.round_sense(selling_price_btc_tmp)}

{oco_text}

{tsl_text}

Available {selling_coin} balance is {purchase_coin_balance}. Use How Many {selling_coin}?
        """
        await message.reply(text, reply_markup=markup)

    except Exception as e:
        logging.error("bn order market buy - MARKET BUY OR SELL ERROR:" + str(e))
        markup = types.ReplyKeyboardRemove()
        await state.finish()
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
                spend = float(data['balance']) * 0.999
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
            
            received, sale_type, symbol, buy_coin, sell_coin = bn_order.create_market_conversion(message.chat.id, data['selling_coin'], spend, data['buying_coin'])
            if data["oco"] == True:
                bn_order.create_oco_conversion(message.chat.id, data['selling_coin'], received, data['buying_coin'])
            elif data["tsl"] == True:
                limit_type = "sell" if sale_type.upper() == "BUY" else "buy"
                await message.reply("Creating Trailing Stop Loss...", reply_markup=markup)
                bn_order.create_trailing_stop_limit(market=symbol, buy_coin=buy_coin, sell_coin=sell_coin, type=limit_type, stop_percentage=0.0099, interval=10)
                
            bn_order.get_wallet(message.chat.id)
            
        await state.finish()
        return await message.reply("Done.", reply_markup=markup)
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


@dp.message_handler(commands=['cancelorders', 'stoporders'])
async def cancel_open_orders(message: types.Message):
    try:
        bn_order.cancel_open_orders(message.chat.id)
    except Exception as e:
        logging.error("START UP ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Start Stream")
