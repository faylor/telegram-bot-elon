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
           
    def create_test_order(self):
        try:
            order = self.client.create_test_order(
                    symbol='BTCUSDT',
                    side=SIDE_BUY,
                    type=ORDER_TYPE_LIMIT,
                    timeInForce=TIME_IN_FORCE_GTC,
                    quantity=100,
                    price='58513.20')
            bot_key = TELEGRAM_BOT
            chat_id = self.chat_ids[0]
            text = "TEST ORDER CREATED: " + json.dumps(order)
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Test Order Failed error:" + str(e))

    def get_wallet(self):
        try:
            info = self.client.get_account()
            balance = self.client.get_asset_balance(asset='BTC')
            trades = self.client.get_my_trades(symbol='BNBBTC')
            bot_key = TELEGRAM_BOT
            chat_id = self.chat_ids[0]
            text = "ACCOUNT INFO: " + json.dumps(info) + "\nBALANCE:" + json.dumps(balance) + "\nTRADES:" + json.dumps(trades)
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

