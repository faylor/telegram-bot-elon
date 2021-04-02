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

    def create_market_buy(self, chat_id, symbol, amount):
        try:
            if self.is_authorized(chat_id):
                symbol = symbol.strip().upper() + "BTC"
                order = self.client.order_market_buy(
                            symbol=symbol,
                            quantity=amount)
                text = "REAL BUY CREATED: " + json.dumps(order)
                self.send_chat_message(text)
        except Exception as e:
            logging.error("Test Order Failed error:" + str(e))
            self.send_chat_message("CREATE ORDER FAILED: " + str(e))

    def create_market_sell(self, chat_id, symbol, amount):
        try:
            if self.is_authorized(chat_id):
                symbol = symbol.strip().upper() + "BTC"
                order = self.client.order_market_sell(
                            symbol=symbol,
                            quantity=amount)
                text = "REAL SELL CREATED: " + json.dumps(order)
                self.send_chat_message(text)
        except Exception as e:
            logging.error("Test Order Failed error:" + str(e))
            self.send_chat_message("CREATE ORDER FAILED: " + str(e))

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
                    r.set(LIVE_ORDER_KEY.format(self.chat_id), json.dumps({"orders": [order]}))
                else:
                    ar = json.loads(saved_orders.decode("utf-8"))
                    ar["orders"].append(order)
                    r.set(LIVE_ORDER_KEY.format(self.chat_id), json.dumps(ar))
                orders = self.client.get_open_orders(symbol=symbol)
                text = "ORDERS: " + json.dumps(orders)
                self.send_chat_message(text)

                order_oco = self.client.create_oco_order(
                        symbol=symbol,
                        side='SELL',
                        quantity=amount,
                        price=float(buy_price) * 1.03,
                        stopPrice=float(buy_price) * 0.99,
                        stopLimitPrice=float(buy_price) * 0.989,
                        stopLimitTimeInForce='GTC')
                text = "OCO ORDERS: " + json.dumps(order_oco)
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

    def get_usd_price(self, symbol):
        usd_price = 0
        try:
            usd_price = self.client.get_symbol_ticker(symbol=symbol.upper() + "USDT")
            return usd_price["price"]
        except Exception as e:
            logging.error("USD Price Failed error:" + symbol + " -- " + str(e))
        return usd_price

    def round_sense(self, price):
        price = float(price)
        if price is None or price == 0:
            return 0
        if price > 100:
            return int(price)
        if price > 10:
            return round(price, 1)
        if price > 1:
            return round(price, 2)
        if price > 0.01:
            return round(price, 4)
        if price > 0.001:
            return round(price, 5)
        return round(price, 8)

    def get_wallet(self, chat_id):
        try:
            if self.is_authorized(chat_id):
                info = self.client.get_account()
                balances = info["balances"]
                # "balances": [{"asset": "BNB", "free": "1014.21000000", "locked": "0.00000000"}, {"asset": "BTC", "free": "0.92797152", "locked": "0.00000000"}, {"asset": "BUSD", "free": "10000.00000000", "locked": "0.00000000"}, {"asset": "ETH", "free": "100.00000000", "locked": "0.00000000"}, {"asset": "LTC", "free": "500.00000000", "locked": "0.00000000"}, {"asset": "TRX", "free": "500000.00000000", "locked": "0.00000000"}, {"asset": "USDT", "free": "10000.00000000", "locked": "0.00000000"}, {"asset": "XRP", "free": "50000.00000000", "locked": "0.00000000"}]
                out = "COIN   FREE     LOCKED     USD\n"
                val = 0
                for b in balances:
                    if b["asset"].upper() in ["BUSD", "USDT"]:
                        usd_price = float(b["free"]) + float(b["locked"])
                    else:
                        usd_price = float(self.get_usd_price(b["asset"]))
                    val = val + usd_price
                    out = out + b["asset"].ljust(8,' ') + str(self.round_sense(b["free"])).ljust(10,' ') + str(self.round_sense(b["locked"])).ljust(10,' ') + "  $" + str(self.round_sense(usd_price)) + "\n"
                out = out + "\nUSD VALUE: $" + str(round(val, 2))
                self.send_chat_message(out)

               
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

    def get_symbol_trades(self, chat_id, symbol):
        try:
            if self.is_authorized(chat_id):
                trades = self.client.get_my_trades(symbol=symbol.upper() + 'BTC')
                out = ""
                for t in trades:
                    if t["isBuyer"] == True:
                        action = "BUY"
                    else:
                        action = "SELL"
                    out = out + t["symbol"] + "  " + action + "  " + t["price"] + "   " + t["qty"] + "\n"
                text = "BTC FREE:" + str(balance["free"]) + " LOCKED: " + str(balance["locked"])  + "\n"
                text = text + "BNB FREE:" + str(bnb_balance["free"]) + " LOCKED: " + str(bnb_balance["locked"]) + "\n"
                text = text + "TRADES:\n" + out
                self.send_chat_message(out)
        except Exception as e:
            logging.error("Failed to get trades for symbol chat message:" + str(e))
            self.send_chat_message("Failed to get trades for " + symbol + " -- " + str(e))
        