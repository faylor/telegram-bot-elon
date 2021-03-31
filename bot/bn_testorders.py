import os
import json
import asyncio
import logging
import requests
from bot.settings import (BN_API_KEY, BN_API_SECRET, TELEGRAM_BOT)
from binance.websockets import BinanceSocketManager
from binance.client import Client
from binance.enums import *
import redis
from .settings import (REDIS_URL)
r = redis.from_url(REDIS_URL)

COIN_DATA_KEY = "STREAM_{}"

class BnOrder():

    def __init__(self) -> None:
        self.chat_ids = []
        self.client = Client(BN_API_KEY, BN_API_SECRET)
        self.bm = BinanceSocketManager(self.client)
        self.last_order_id = None
           
    def create_test_order(self, chat_id, symbols, buy_price, amount):
        try:
            order = self.client.create_test_order(
                    symbol=symbols,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_LIMIT,
                    timeInForce=TIME_IN_FORCE_GTC,
                    quantity=amount,
                    price=buy_price)
            bot_key = TELEGRAM_BOT
            text = "TEST ORDER CREATED: " + json.dumps(order)
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Test Order Failed error:" + str(e))

    def create_order(self, chat_id, symbols, buy_price, amount):
        try:
            order = self.client.order_limit_buy(
                        symbol=symbols,
                        quantity=amount,
                        price=buy_price)
            bot_key = TELEGRAM_BOT
            text = "TEST ORDER CREATED: " + json.dumps(order)
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
            resp = requests.post(send_message_url)

            self.last_order_id = order

            orders = self.client.get_open_orders(symbol='WRXBNB')
            bot_key = TELEGRAM_BOT
            text = "ORDERS: " + json.dumps(orders)
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Test Order Failed error:" + str(e))

    def check_orders(self, chat_id):
        try:
            orders = self.client.get_open_orders(symbol='WRXBNB')
            bot_key = TELEGRAM_BOT
            text = "ORDERS: " + json.dumps(orders)
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Check Order Failed error:" + str(e))

    def cancel_order(self, chat_id):
        try:
            if self.last_order_id is not None:
                result = self.client.cancel_order(symbol='BNBBTC', orderId=self.last_order_id)
                bot_key = TELEGRAM_BOT
                text = "CANCEL RESULT: " + json.dumps(result)
                send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Cancel Order Failed error:" + str(e))


    def get_wallet(self, chat_id):
        try:
            # info = self.client.get_account()
            balance = self.client.get_asset_balance(asset='BNB')
            trades = self.client.get_my_trades(symbol='BNBBTC')
            bot_key = TELEGRAM_BOT
            text = "ACCOUNT BNB BALANCE:" + str(balance) + "\nTRADES:" + json.dumps(trades)
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Account settings error:" + str(e))
   
    def add_chat_id(self, chat_id):
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)

    def remove_chat_id(self, chat_id):
        if chat_id in self.chat_ids:
            self.chat_ids.remove(chat_id)

