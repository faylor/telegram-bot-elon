from binance.client import Client
from .settings import TELEGRAM_BOT
import time
import logging
import json
import requests
import asyncio


class TrailingStopLimit():

    def __init__(self, chat_id, client: Client, market, buy_coin, sell_coin, type, stop_percentage, interval):
        self.client = client
        self.chat_id = chat_id
        self.market = market
        self.buy_coin = buy_coin
        self.sell_coin = sell_coin
        self.type = type
        self.stop_percentage = stop_percentage
        self.interval = interval
        self.running = False
        self.stoploss = self.initialize_stop()
        self.verbose = False
        self.last_message_count = 0
        self.first_price = None
        self.breakeven = None
    

    def get_price(self, market):
        try:
            result = self.client.get_symbol_ticker(symbol=market)
            return float(result['price'])
        except Exception as e:
            logging.error("Symbol ticker failed:" + str(e))
            return None

    def get_balance(self, coin):
        bal = self.client.get_asset_balance(coin.upper())
        return float(bal['free'])

    def initialize_stop(self):
        price = self.get_price(self.market)
        self.breakeven = price * 1.0025
        self.first_price = price
        delta = self.stop_percentage * price
        if self.type == "sell":
            delta = -1 * delta
        return price + delta

    def update_stop(self):
        price = self.get_price(self.market)
        if price is None:
            logging.error("Price empty, need to cool off maybe.")
            return
        if self.breakeven is None:
            self.breakeven = price * 1.0025
            self.first_price = price
        delta = self.stop_percentage * price
        if self.type == "sell":
            if price < self.breakeven and (price - delta) > self.stoploss:
                self.stoploss = price - delta
                self.send_chat_message("Below breakeven (tight). New high observed: Updating stop loss to %.8f - breakeven %.8f" % (self.stoploss, self.breakeven))
            elif price >= self.breakeven and (price - delta/5) > self.stoploss:
                self.stoploss = price - delta/5
                self.send_chat_message("Above Breakeven (loose). New high observed: Updating stop loss to %.8f - breakeven %.8f" % (self.stoploss, self.breakeven))
            elif price >= self.breakeven and (price - delta/2) > self.stoploss:
                self.stoploss = price - delta/2
                self.send_chat_message("Above Breakeven. New high observed: Updating stop loss to %.8f - breakeven %.8f" % (self.stoploss, self.breakeven))
            elif price <= self.stoploss:
                self.running = False
                amount = self.get_balance(self.buy_coin)
                # price = self.get_price(self.market)
                # price_str = "{:0.0{}f}".format(price * 0.9999, 8)
                # order = self.client.order_limit_sell(
                #             symbol=self.market,
                #             quantity=amount,
                #             price=price_str)
                order = self.client.order_market_sell(symbol=self.market, quantity=amount)
                self.send_chat_message("Sell triggered | Price: %.8f  | Stop loss: %.8f" % (price, self.stoploss))
        elif self.type == "buy":
            if (price + delta) < self.stoploss and price < self.breakeven:
                self.stoploss = price + delta
                self.send_chat_message("New low observed: Updating stop loss to %.8f" % self.stoploss)
            elif price >= self.stoploss:
                self.running = False
                balance = self.get_balance(self.sell_coin)
                # price = self.get_price(self.market)
                # price_str = "{:0.0{}f}".format(price, 8)
                amount = (balance / price) * 0.999 # 0.10% maker/taker fee without BNB
                # order = self.client.order_limit_buy(
                #             symbol=self.market,
                #             quantity=amount,
                #             price=price_str)
                order = self.client.order_market_buy(symbol=self.market, quantity=amount)
                self.send_chat_message("Buy triggered | Price: %.8f | Stop loss: %.8f" % (price, self.stoploss))

    def send_chat_message(self, text):
        try:
            bot_key = TELEGRAM_BOT
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={self.chat_id}&text={text}&parse_mode=HTML'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Failed to send chat message:" + str(e))

    def print_status(self):
        self.last_message_count = self.last_message_count + 1
        if self.verbose or self.last_message_count > 14:
            last = self.get_price(self.market)
            if self.first_price is not None and self.first_price > 0:
                diff = round(100 * (last - self.first_price)/self.first_price, 2)
            else:
                diff = 0
            price_str = "{:0.0{}f}".format(last, 8)
            text = f"Elon's Running a TSL- {self.type} {self.market} @ BTC{price_str}. Change: {diff}%  Limit: {self.stoploss}"
            self.send_chat_message(text)
            self.last_message_count = 0
        else:
            logging.info("Still running TSL for " + self.market)
