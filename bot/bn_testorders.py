import os
import json
import asyncio
import logging
import requests
from bot.settings import (BN_TEST_API_KEY, BN_TEST_API_SECRET, BN_CHAT_ID, BN_API_KEY, BN_API_SECRET, TELEGRAM_BOT)
from binance.websockets import BinanceSocketManager
from binance.client import Client
from binance.enums import *
import redis
from .settings import (REDIS_URL)
r = redis.from_url(REDIS_URL)

COIN_DATA_KEY = "STREAM_{}"
LIVE_ORDER_KEY = "LIVE_{}"

class BnOrder():

    def __init__(self) -> None:
        self.chat_id = BN_CHAT_ID
        self.client = Client(BN_TEST_API_KEY, BN_TEST_API_SECRET)
        self.bm = BinanceSocketManager(self.client)
        self.last_order_id = None
        self.client.API_URL = 'https://testnet.binance.vision/api'
           
    def create_test_order(self, chat_id, symbol, buy_price, amount):
        try:
            if self.is_authorized(chat_id):
                symbol = symbol.strip().upper() + "BTC"
                logging.error("SYMBOL: " + symbol)
                
                order = self.client.create_test_order(
                        symbol=symbol,
                        side=SIDE_BUY,
                        type=ORDER_TYPE_LIMIT,
                        timeInForce=TIME_IN_FORCE_GTC,
                        quantity=amount,
                        price=buy_price)
                text = "TEST ORDER CREATED: " + json.dumps(order)
                self.send_chat_message(text)
        except Exception as e:
            logging.error("Test Order Failed error:" + str(e))
            self.send_chat_message("CREATE TEST ORDER FAILED: " + str(e))

    def create_order(self, chat_id, symbol, buy_price, amount):
        try:
            if self.is_authorized(chat_id):
                symbol = symbol.strip().upper() + "BTC"
                order = self.client.order_limit_buy(
                            symbol=symbol,
                            quantity=amount,
                            price=buy_price)
                text = "REAL ORDER CREATED: " + json.dumps(order)
                self.send_chat_message(text)

                self.last_order_id = order['orderId']
                saved_orders = r.get(LIVE_ORDER_KEY.format(self.chat_id))
                if saved_orders is None:
                    r.set(LIVE_ORDER_KEY.format(self.chat_id), [order])
                else:
                    ar = json.loads(saved_orders.decode("utf-8"))
                    ar.append(order)
                    r.set(LIVE_ORDER_KEY.format(self.chat_id), json.dumps(ar))
                orders = self.client.get_open_orders(symbol=symbol)
                text = "ORDERS: " + json.dumps(orders)
                self.send_chat_message(text)
        except Exception as e:
            logging.error("Test Order Failed error:" + str(e))
            self.send_chat_message("CREATE ORDER FAILED: " + str(e))

    def check_orders(self, chat_id):
        try:
            if self.is_authorized(chat_id):
                orders = self.client.get_open_orders()
                text = "ORDERS: " + json.dumps(orders)
                self.send_chat_message(text)
                
                saved_orders = r.get(LIVE_ORDER_KEY.format(self.chat_id))
                if saved_orders is not None:
                    ar = json.loads(saved_orders.decode("utf-8"))
                    self.send_chat_message("SAVED ORDERS: " + json.dumps(ar))

        except Exception as e:
            logging.error("Check Order Failed error:" + str(e))
            self.send_chat_message("CHECK ORDERS FAILED: " + str(e))

    def cancel_open_orders(self, chat_id):
        try:
            if self.is_authorized(chat_id):
                orders = self.client.get_open_orders()
                for order in orders:
                    result = self.client.cancel_order(symbol=order['symbol'], orderId=order["orderId"])
                    text = "CANCEL RESULT: " + json.dumps(result)
                    self.send_chat_message(text)
        except Exception as e:
            logging.error("Cancel Order Failed error:" + str(e))
            self.send_chat_message("FAILED TO CANCEL ORDER: " + str(e))

    def get_wallet(self, chat_id):
        try:
            if self.is_authorized(chat_id):
                # info = self.client.get_account()
                balance = self.client.get_asset_balance(asset='BTC')
                bnb_balance = self.client.get_asset_balance(asset='BNB')
                trades = self.client.get_my_trades(symbol='BNBBTC')
                text = "BTC BALANCE:" + str(balance) + "\nBNB BALANCE:" + str(bnb_balance) + "\nTRADES:\n" + json.dumps(trades)
                self.send_chat_message(text)
        except Exception as e:
            logging.error("Account settings error:" + str(e))
            self.send_chat_message("FAILED TO GET WALLET: " + str(e))
   
    def send_chat_message(self, text):
        try:
            bot_key = TELEGRAM_BOT
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={self.chat_id}&text={text}'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Failed to send chat message:" + str(e))

    def is_authorized(self, chat_id):
        if self.chat_id is None or int(self.chat_id) != int(chat_id):
            raise Exception("Unauthorized Chat:" + str(chat_id) + " != " + str(self.chat_id))
        return True
