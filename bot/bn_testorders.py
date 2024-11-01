import os
import json
import asyncio
import logging
import datetime
import math
import requests
from bot.settings import (BN_TEST_API_KEY, BN_TEST_API_SECRET, BN_CHAT_ID, BN_CHAT_ID_GROUP, BN_API_KEY, BN_API_SECRET, TELEGRAM_BOT)
from binance import BinanceSocketManager
from binance.client import Client
from binance.enums import *
from .bn_userSocket import bn_UserSocket
from .bn_trailingStopLimit import TrailingStopLimit
import redis
import time
from .settings import (REDIS_URL)
r = redis.from_url(REDIS_URL, ssl_cert_reqs=None)

COIN_DATA_KEY = "STREAM_{}"
LIVE_ORDER_KEY = "LIVE_{}"

def fire_and_forget(f):
    def wrapped(*args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(None, f, *args, *kwargs)
    return wrapped

FORCE_STOP = False

@fire_and_forget
def run(tsl: TrailingStopLimit):
    FORCE_STOP = False
    tsl.running = True
    while (tsl.running and FORCE_STOP == False):
        tsl.print_status()
        tsl.update_stop()
        time.sleep(tsl.interval)

class BnOrder():

    def __init__(self) -> None:
        self.chat_id = BN_CHAT_ID_GROUP
        # self.chat_id = BN_CHAT_ID 
        self.client = Client(BN_API_KEY, BN_API_SECRET)
        # self.client = Client(BN_TEST_API_KEY, BN_TEST_API_SECRET)
        # self.client.API_URL = 'https://testnet.binance.vision/api'
        self.client.PUBLIC_API_VERSION = "v3"
        self.bm = bn_UserSocket(self.client)
        self.tso = None
        
    def process_message(self, msg):
        try:
            self.send_chat_message("Account Update:\n" + json.dumps(msg))
        except Exception as e:
            logging.error("Process Account Update Error:" + str(e))
            self.send_chat_message("Process Account Update Error: " + str(e))

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

    def create_market_buy(self, chat_id, symbol, amount, to_currency = "BTC"):
        try:
            if self.is_authorized(chat_id):
                symbol = symbol.strip().upper() + to_currency.strip().upper()
                amount = round(amount, 8)
                order = self.client.order_market_buy(
                            symbol=symbol,
                            quantity=amount)
                text = "REAL BUY CREATED: " + json.dumps(order)
                self.send_chat_message(text)
        except Exception as e:
            logging.error("Test Order Failed error:" + str(e))
            self.send_chat_message("CREATE ORDER FAILED: " + str(e))
            raise e

    def get_exchange_symbol(self, sell_coin, buy_coin):
        try:
            symbol = buy_coin.strip().upper() + sell_coin.strip().upper()
            info = self.client.get_symbol_info(symbol)
            if info is not None:
                result = self.client.get_symbol_ticker(symbol=symbol)
                s, t = self.get_step_size(info)
                return symbol, "BUY", result["price"], info, s, t
        except Exception as e:
            logging.error("Symbol fail:" + str(e))

        try:
            symbol = sell_coin.strip().upper() + buy_coin.strip().upper()
            info = self.client.get_symbol_info(symbol)
            if info is not None:
                result = self.client.get_symbol_ticker(symbol=symbol)
                s, t = self.get_step_size(info)
                return symbol, "SELL", result["price"], info, s, t
        except Exception as e:
            logging.error("Symbol fail:" + str(e))
            raise e

    def get_step_size(self, info):
        step_size = 0.0
        tick_size = 0.0
        logging.error("INFO:" + json.dumps(info))
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
            if f['filterType'] == 'PRICE_FILTER':
                tick_size = float(f['tickSize'])
        return step_size, tick_size

    def create_market_conversion(self, chat_id, sell_coin, total_spend, buy_coin):
        try:
            if self.is_authorized(chat_id):
                symbol, sale_type, price, _, step_size, _ = self.get_exchange_symbol(sell_coin, buy_coin)
                precision = int(round(-math.log(step_size, 10), 0))
                
                logging.error("AMOUNT:" + str(total_spend))
                logging.error("step_size:" + str(step_size))
                logging.error("precision:" + str(precision))
                
                logging.error("SALE TYPE:" + str(sale_type))
                if sale_type == "SELL":
                    amt_str = "{:0.0{}f}".format(total_spend, precision)
                    logging.error("QUANTITY:" + str(amt_str))
                    order = self.client.order_market_sell(
                                symbol=symbol,
                                quantity=amt_str)
                    text = "SELL " + str(amt_str)+ " of " + symbol + "\nOrderId:" + str(order["orderId"]) + " STATUS:" + str(order["status"])  + "\nFILLS:\n" + json.dumps(order["fills"])

                else:
                    amount = total_spend / float(price)
                    amt_str = "{:0.0{}f}".format(amount, precision)
                    logging.error("QUANTITY:" + str(amt_str))
                    order = self.client.order_market_buy(
                                symbol=symbol,
                                quantity=amt_str)
                    text = "BUY " + str(amt_str)+ " of " + symbol + "\nOrderId:" + str(order["orderId"]) + " STATUS:" + str(order["status"])  + "\nFILLS:\n" + json.dumps(order["fills"])
                self.send_chat_message(text)
                return amt_str, sale_type, symbol, buy_coin, sell_coin
        except Exception as e:
            logging.error("Order Failed error:" + str(e))
            self.send_chat_message("CREATE ORDER FAILED: " + str(e))
            raise e

    def create_trailing_stop_limit(self, market, buy_coin, sell_coin, type, stop_percentage, interval):
        try:
            if self.tso is not None and self.tso.running is True:
                self.send_chat_message("OPEN Trailing Stop Limit, Cancel First. ")
            else:
                self.tso = TrailingStopLimit(chat_id=self.chat_id, client=self.client, market=market, buy_coin=buy_coin, sell_coin=sell_coin, type=type, stop_percentage=stop_percentage, interval=interval)
                run(self.tso)
        except Exception as e:
            logging.error("Order Failed error:" + str(e))
            self.send_chat_message("CREATE ORDER FAILED: " + str(e))
            raise e
                
    def create_oco_conversion(self, chat_id, sell_coin, amount, buy_coin):
        try:
            if self.is_authorized(chat_id):
                symbol, sale_type, price, info, step_size, price_tick_size  = self.get_exchange_symbol(sell_coin, buy_coin)
                precision = int(round(-math.log(step_size, 10), 0))
                amt_str = "{:0.0{}f}".format(float(amount), precision)
                price_precision = int(round(-math.log(price_tick_size, 10), 0))
                logging.error("QUANTITY:" + str(amt_str))    
                if sale_type == "SELL":
                    # BUY Orders: Limit Price < Last Price < Stop Price
                    sell_price = "{:0.0{}f}".format(float(price) * 0.97, price_precision)
                    stop_price = "{:0.0{}f}".format(float(price) * 1.01, price_precision)
                    stop_limit_price = "{:0.0{}f}".format(float(price) * 1.01, price_precision)
                    order_oco = self.client.create_oco_order(
                        symbol=symbol,
                        side='BUY',
                        quantity=amt_str,
                        price=sell_price,
                        stopPrice=stop_price,
                        stopLimitPrice=stop_limit_price,
                        stopLimitTimeInForce='GTC')
                else:
                    # TODO check filters
                    # quantity >= minQty
                    # quantity <= maxQty
                    # (quantity-minQty) % stepSize == 0
                    # SELL Orders: Limit Price > Last Price > Stop Price
                    sell_price = "{:0.0{}f}".format(float(price) * 1.03, price_precision)
                    stop_price = "{:0.0{}f}".format(float(price) * 0.99, price_precision)
                    stop_limit_price = "{:0.0{}f}".format(float(price) * 0.989, price_precision)
                    logging.error("CURRENT PRICE: " + str(price) + "   SELL PRICE: " + str(sell_price) + "  STOP PRICE:" + str(stop_price) + "  STOP LIMIT PRICE:" + str(stop_limit_price))
                    order_oco = self.client.create_oco_order(
                        symbol=symbol,
                        side='SELL',
                        quantity=amt_str,
                        price=sell_price,
                        stopPrice=stop_price,
                        stopLimitPrice=stop_limit_price,
                        stopLimitTimeInForce='GTC')
                
                oco_text = order_oco["listOrderStatus"] + " " + self.format_orders(order_oco["orderReports"])
                self.send_chat_message(oco_text)
        except Exception as e:
            logging.error("OCO Failed error:" + str(e))
            self.send_chat_message("CREATE OCO FAILED: " + str(e))
            raise e


    def format_orders(self, orders):
        oco_text = "OPEN ORDERS:\n" 
        for o in orders:
            if o["type"] == "STOP_LOSS_LIMIT":
                oco_text = oco_text + "\nSTOP LOSS:\n" + o["side"] + " " + o["symbol"] + "- Stop Limit: " + o["stopPrice"] + " Price: " + o["price"] + " Qty:" + o["origQty"] + "\n"
            elif o["type"] == "LIMIT_MAKER":
                oco_text = oco_text + "\nPROFIT:\n" + o["side"]  + " " + o["symbol"] + "- Price: " + o["price"] + " Qty:" + o["origQty"] + "\n"
            else:
                oco_text = oco_text + "\n" + json.dumps(o) + "\n"
        oco_text = oco_text + "\nCheck Order Status with: /checkorders\n" 
        oco_text = oco_text + "\nCancel All Orders with: /cancelorders\n" 
        return oco_text

    def create_order(self, chat_id, selling_coin, buying_coin, price, amount):
        try:
            if self.is_authorized(chat_id):
                symbol, sale_type, price, info, step_size = self.get_exchange_symbol(selling_coin, buying_coin)
                precision = int(round(-math.log(step_size, 10), 0))
                if sale_type == "SELL":
                    amt_str = "{:0.0{}f}".format(float(amount), precision)
                    order = self.client.order_limit_sell(
                            symbol=symbol,
                            quantity=amt_str,
                            price=round(float(price), 5))
                else:
                    amt_str = "{:0.0{}f}".format(float(amount), precision)
                    order = self.client.order_limit_buy(
                            symbol=symbol,
                            quantity=amt_str,
                            price=round(float(price), 5))
                text = "LIMIT ORDER CREATED:\n" + json.dumps(order)
                self.send_chat_message(text)

                # self.last_order_id = order['orderId']
                # saved_orders = r.get(LIVE_ORDER_KEY.format(self.chat_id))
                # if saved_orders is None:
                #     r.set(LIVE_ORDER_KEY.format(self.chat_id), json.dumps({"orders": [order]}))
                # else:
                #     ar = json.loads(saved_orders.decode("utf-8"))
                #     ar["orders"].append(order)
                #     r.set(LIVE_ORDER_KEY.format(self.chat_id), json.dumps(ar))
                self.check_orders(chat_id=chat_id)
                
        except Exception as e:
            logging.error("Test Order Failed error:" + str(e))
            self.send_chat_message("CREATE ORDER FAILED: " + str(e))

    def check_orders(self, chat_id):
        try:
            if self.is_authorized(chat_id):
                orders = self.client.get_open_orders()
                self.send_chat_message(self.format_orders(orders))
                
                # saved_orders = r.get(LIVE_ORDER_KEY.format(self.chat_id))
                # if saved_orders is not None:
                #     ar = json.loads(saved_orders.decode("utf-8"))
                #     self.send_chat_message("SAVED ORDERS: " + json.dumps(ar))

        except Exception as e:
            logging.error("Check Order Failed error:" + str(e))
            self.send_chat_message("CHECK ORDERS FAILED: " + str(e))

    def cancel_open_orders(self, chat_id):
        try:
            if self.is_authorized(chat_id):
                if self.tso is not None:
                    self.tso.running = False
                    FORCE_STOP = True
                orders = self.client.get_open_orders()
                for order in orders:
                    result = self.client.cancel_order(symbol=order['symbol'], orderId=order["orderId"])
                    text = "CANCEL RESULT:\n" + json.dumps(result)
                    self.send_chat_message(text)
                
        except Exception as e:
            logging.error("Cancel Order Failed error:" + str(e))
            orders = self.client.get_open_orders()
            if len(orders) > 0:
                self.send_chat_message("FAILED TO CANCEL ORDER: " + str(e))

    def get_usd_price(self, symbol):
        usd_price = 0
        try:
            usd_price = self.client.get_symbol_ticker(symbol=symbol.upper() + "USDT")
            return usd_price["price"]
        except Exception as e:
            logging.error("USD Price Failed error:" + symbol + " -- " + str(e))
        return usd_price

    def get_btc_price(self, symbol):
        btc_price = 0
        try:
            btc_price = self.client.get_symbol_ticker(symbol=symbol.upper() + "BTC")
            return btc_price["price"]
        except Exception as e:
            logging.error("BTC Price Failed error:" + symbol + " -- " + str(e))
        return btc_price

    def round_sense(self, price):
        price = float(price)
        if price is None or price == 0:
            return 0
        if price > 1000:
            return int(price)
        if price > 100:
            return round(price, 1)
        if price > 10:
            return round(price, 2)
        if price > 0.01:
            return round(price, 4)
        if price > 0.001:
            return round(price, 5)
        return round(price, 8)

    def get_user_balance(self, symbol):
        try:
            balance = self.client.get_asset_balance(asset=symbol)
            logging.error("CHeck" + json.dumps(balance))
            return float(balance["free"])
        except Exception as e:
            logging.error("Account settings error:" + str(e))
            self.send_chat_message("FAILED TO GET BALANCE: " + str(e))
            return 0


    def get_wallet(self, chat_id):
        try:
            if self.is_authorized(chat_id):
                info = self.client.get_account()
                balances = info["balances"]
                # "balances": [{"asset": "BNB", "free": "1014.21000000", "locked": "0.00000000"}, {"asset": "BTC", "free": "0.92797152", "locked": "0.00000000"}, {"asset": "BUSD", "free": "10000.00000000", "locked": "0.00000000"}, {"asset": "ETH", "free": "100.00000000", "locked": "0.00000000"}, {"asset": "LTC", "free": "500.00000000", "locked": "0.00000000"}, {"asset": "TRX", "free": "500000.00000000", "locked": "0.00000000"}, {"asset": "USDT", "free": "10000.00000000", "locked": "0.00000000"}, {"asset": "XRP", "free": "50000.00000000", "locked": "0.00000000"}]
                out = "<pre>FREE       LOCKED      BTC      USD\n"
                val = 0
                btc_val = 0
                for b in balances:
                    quantity = float(b["free"]) + float(b["locked"])
                    if quantity > 0:
                        if b["asset"].upper() != "BETH":
                            usd_price = float(self.get_usd_price(b["asset"]))
                            btc_price = float(self.get_btc_price(b["asset"]))
                            if b["asset"].upper() in ["BUSD", "USDT"]:
                                usd_value = float(b["free"]) + float(b["locked"])
                                if btc_price > 0:
                                    btc_value = usd_value/btc_price
                                else:
                                    btc_value = 0
                            else:
                                usd_value = usd_price * quantity
                                if b["asset"].upper() == "BTC":
                                    btc_price = 1
                                    btc_value = float(b["free"]) + float(b["locked"])   
                                else:
                                    btc_value = btc_price * quantity
                            val = val + usd_value
                            btc_val = btc_val + btc_value
                            out = out + "\n" + b["asset"] + " @ $" + str(round(usd_price, 2)) + " BTC" + str(btc_price) + "\n" 
                            out = out + str(self.round_sense(b["free"])).ljust(10,' ') + " " + str(self.round_sense(b["locked"])).ljust(8,' ') + " " + str(self.round_sense(btc_value)).ljust(8,' ') + " " + str(self.round_sense(usd_value)) + "\n"
                out = out + "</pre>\n$" + str(round(val, 2)) + "\n₿" + str(round(btc_val, 6))
                self.send_chat_message(out)

               
        except Exception as e:
            logging.error("Account settings error:" + str(e))
            self.send_chat_message("FAILED TO GET WALLET: " + str(e))
   
    def send_chat_message(self, text):
        try:
            bot_key = TELEGRAM_BOT
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={self.chat_id}&text={text}&parse_mode=HTML'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Failed to send chat message:" + str(e))

    def is_authorized(self, chat_id):
        if self.chat_id is None or int(self.chat_id) != int(chat_id):
            raise Exception("Unauthorized Chat, use only correct chat.")
        starter = self.bm.start_user_socket(self.process_message)
        logging.error("Stream resp:" + str(starter))
        return True

    def get_symbol_trades(self, chat_id, symbol):
        try:
            if self.is_authorized(chat_id):
                trades = self.client.get_my_trades(symbol=symbol.upper() + 'BTC')
                if len(trades) > 0:
                    sorted_trades = sorted(trades, key=lambda k: k['time'], reverse=True)
                    out = "<pre>DATE TIME    SYMBOL   SIDE    PRICE     QUANTITY\n"
                    for t in sorted_trades:
                        if t["isBuyer"] == True:
                            action = "BUY"
                        else:
                            action = "SELL"
                        time_str = datetime.datetime.fromtimestamp(int(t["time"])/1000).strftime('%d-%m %H:%M')
                        out = out + time_str + "  " + t["symbol"] + "  " + action + "  " + t["price"] + "   " + t["qty"] + "\n"
                    out = "TRADES vs BTC:\n" + out + "</pre>"
                    self.send_chat_message(out)

                trades = self.client.get_my_trades(symbol=symbol.upper() + 'USDT')
                if len(trades) > 0:
                    sorted_trades = sorted(trades, key=lambda k: k['time'], reverse=True)
                    out = "<pre>DATE TIME    SYMBOL   SIDE    PRICE     QUANTITY\n"
                    for t in sorted_trades:
                        if t["isBuyer"] == True:
                            action = "BUY"
                        else:
                            action = "SELL"
                        time_str = datetime.datetime.fromtimestamp(int(t["time"])/1000).strftime('%d-%m %H:%M')
                        out = out + time_str + "  " + t["symbol"] + "  " + action + "  " + t["price"] + "   " + t["qty"] + "\n"
                    out = "TRADES vs USDT:\n" + out + "</pre>"
                    self.send_chat_message(out)
        except Exception as e:
            logging.error("Failed to get trades for symbol chat message:" + str(e))
            self.send_chat_message("Failed to get trades for " + symbol + " -- " + str(e))
        