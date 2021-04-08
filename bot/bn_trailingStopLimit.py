from binance.client import Client
from .settings import TELEGRAM_BOT
import time
import logging
import json
import requests
import asyncio


class TrailingStopLimit():

    def __init__(self, chat_id, client: Client, market, buy_coin, sell_coin, type, stopsize, interval):
        self.client = client
        self.chat_id = chat_id
        self.market = market
        self.buy_coin = buy_coin
        self.sell_coin = sell_coin
        self.type = type
        self.stopsize = stopsize
        self.interval = interval
        self.running = False
        self.stoploss = self.initialize_stop()
    
    

    def get_price(self, market):
        result = self.client.get_symbol_ticker(symbol=market)
        return float(result['price'])

    def get_balance(self, coin):
        bal = self.client.get_asset_balance(coin.upper())
        return float(bal['free'])

    def initialize_stop(self):
        if self.type == "buy":
            return (self.get_price(self.market) + self.stopsize)
        else:
            return (self.get_price(self.market) - self.stopsize)

    def update_stop(self):
        price = self.get_price(self.market)
        if self.type == "sell":
            if (price - self.stopsize) > self.stoploss:
                self.stoploss = price - self.stopsize
                self.send_chat_message("New high observed: Updating stop loss to %.8f" % self.stoploss)
            elif price <= self.stoploss:
                self.running = False
                amount = self.get_balance(self.buy_coin)
                price = self.get_price(self.market)
                order = self.client.order_limit_sell(
                            symbol=self.market,
                            quantity=amount,
                            price=price)
                self.send_chat_message("Sell triggered | Price: %.8f | Stop loss: %.8f" % (price, self.stoploss))
        elif self.type == "buy":
            logging.error("e")
            if (price + self.stopsize) < self.stoploss:
                logging.error("f")
                self.stoploss = price + self.stopsize
                self.send_chat_message("New low observed: Updating stop loss to %.8f" % self.stoploss)
            elif price >= self.stoploss:
                self.running = False
                balance = self.get_balance(self.sell_coin)
                price = self.get_price(self.market)
                amount = (balance / price) * 0.999 # 0.10% maker/taker fee without BNB
                order = self.client.order_limit_buy(
                            symbol=self.market,
                            quantity=amount,
                            price=price)
                self.send_chat_message("Buy triggered | Price: %.8f | Stop loss: %.8f" % (price, self.stoploss))

    def send_chat_message(self, text):
        try:
            bot_key = TELEGRAM_BOT
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={self.chat_id}&text={text}&parse_mode=HTML'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Failed to send chat message:" + str(e))

    def print_status(self):
        last = self.get_price(self.market)
        self.send_chat_message(f"""---------------------
Trail type: {self.type}
Market: {self.market}
Stop loss: {self.stoploss}
Last price: {last}
Stop size: {self.stopsize}
---------------------""")
