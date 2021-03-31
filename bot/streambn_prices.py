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

class Bntream():

    def __init__(self) -> None:
        self.chat_ids = []
        self.client = Client(BN_API_KEY, BN_API_SECRET)
        self.bm = BinanceSocketManager(self.client)
        self.volumes = []
        self.stored = 0
        self.last_average = 0
        self.volume_count = 0
        self.sell_updates = 0
        self.buy_updates = 0
        self.conn_key = ""
        self.conn_mt_key = ""
        self.green_count = {}
        self.red_count = {}
        self.velocity = {}
        self.velocity_previous = {}
        self.miniticker = {}
           
    def process_message(self, msg):
        try:
            stream, data = msg['stream'], msg['data']
            taker_buy_vol = float(data["k"]["Q"])
            is_end = data["k"]["x"]
            symbol = stream.lower().replace("usdt@kline_1m", "")
            if is_end == True:
                open_price = float(data["k"]["o"])
                close_price = float(data["k"]["c"])
                if stream in self.velocity:
                    self.velocity_previous[stream] = self.velocity[stream]
                self.velocity[stream] = (close_price - open_price)/1 # 1min

                if close_price > open_price:
                    if stream in self.green_count:
                        self.green_count[stream] = self.green_count[stream] + 1
                    else:
                        self.green_count[stream] = 1
                    self.red_count[stream] = 0
                    logging.error("PUMP UP!")
                else:
                    if stream in self.red_count:
                        self.red_count[stream] = self.red_count[stream] + 1
                    else:
                        self.red_count[stream] = 1
                    self.green_count[stream] = 0
                    logging.error("DUMP Down!")
                
                data_db = r.get(COIN_DATA_KEY.format("AUDIO"))
                if data_db is not None:
                    js = json.loads(data_db.decode("utf-8"))
                    if "Q" in js:
                        if js["Q"] is None:
                            js = {"Q": [taker_buy_vol]}
                        else:
                            if len(js["Q"]) > 1:
                                last_VOL = float(js["Q"][-1])
                                if last_VOL > 0:
                                    diff = 100 * (taker_buy_vol - last_VOL)/last_VOL
                                else:
                                    diff = 0
                                if abs(diff) > 10000:
                                    bot_key = TELEGRAM_BOT
                                    chat_id = self.chat_ids[0]
                                    text = stream.replace("usdt@kline_1m", "").upper() + " VOLUME RAPID CHANGE " + str(round(float(diff),1)) + "%"
                                    send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                                    resp = requests.post(send_message_url)
                            if len(js["Q"]) > 50:
                                js["Q"] = js["Q"][:25]
                            js["Q"].append(taker_buy_vol) 
                    else:
                        js = {"Q": [taker_buy_vol]}
                else:
                    js = {"Q": [taker_buy_vol]}
                r.set(COIN_DATA_KEY.format("AUDIO"), json.dumps(js))
                self.stored = self.stored + 1
            elif stream in self.green_count and self.green_count[stream] > 1 and self.velocity[stream]  > self.velocity_previous[stream]:
                if symbol in self.miniticker:
                    high_to_low_diff = float(self.miniticker[symbol]["h"]) - float(self.miniticker[symbol]["l"])
                    high_to_price_diff = float(self.miniticker[symbol]["h"]) - float(data["k"]["c"])
                    low_to_price_diff = float(data["k"]["c"]) - float(self.miniticker[symbol]["l"])
                    bot_key = TELEGRAM_BOT
                    chat_id = self.chat_ids[0]
                    ratio = self.velocity[stream]/self.velocity_previous[stream]
                    text = f"""{symbol} {self.green_count[stream]}  GREEN\n 
                            24hr High - 24hr Low: {round(high_to_low_diff, 4)}\n
                            24hr High - Price: {round(high_to_price_diff, 4)}\n
                            Price - 24hr Low: {round(low_to_price_diff, 4)}\n
                            Velocity: {round(ratio,1)}\n
                            Buy Vol: {round(float(taker_buy_vol),1)}
                    """
                    send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                    resp = requests.post(send_message_url)
                    self.green_count[stream] = 0
            elif stream in self.red_count and self.red_count[stream] > 1 and self.velocity[stream] < self.velocity_previous[stream]:
                high_to_low_diff = float(self.miniticker[symbol]["h"]) - float(self.miniticker[symbol]["l"])
                high_to_price_diff = float(self.miniticker[symbol]["h"]) - float(data["k"]["c"])
                low_to_price_diff = float(data["k"]["c"]) - float(self.miniticker[symbol]["l"])
                bot_key = TELEGRAM_BOT
                chat_id = self.chat_ids[0]
                ratio = self.velocity[stream]/self.velocity_previous[stream]
                text = f"""{symbol} {self.green_count[stream]}  RED\n 
                        24hr High - 24hr Low: {round(high_to_low_diff, 4)}\n
                        24hr High - Price: {round(high_to_price_diff, 4)}\n
                        Price - 24hr Low: {round(low_to_price_diff, 4)}\n
                        Velocity: {round(ratio,1)}\n
                        Buy Vol: {round(float(taker_buy_vol),1)}
                """
                send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                resp = requests.post(send_message_url)
                self.red_count[stream] = 0
        except Exception as e:
            logging.error("BN Stream process error:" + str(e))
        # do something

    def process_miniticker(self, msg):
        try:
            stream, data = msg['stream'], msg['data']
            #    {
            #     "e": "24hrMiniTicker",  // Event type
            #     "E": 123456789,         // Event time
            #     "s": "BNBBTC",          // Symbol
            #     "c": "0.0025",          // Close price
            #     "o": "0.0010",          // Open price
            #     "h": "0.0025",          // High price
            #     "l": "0.0010",          // Low price
            #     "v": "10000",           // Total traded base asset volume
            #     "q": "18"               // Total traded quote asset volume
            #   }
            symbol = data["s"].lower().replace("usdt", "")
            self.miniticker[symbol] = data
        except Exception as e:
            logging.error("BN MT Stream process error:" + str(e))

   
    def add_chat_id(self, chat_id):
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)

    def remove_chat_id(self, chat_id):
        if chat_id in self.chat_ids:
            self.chat_ids.remove(chat_id)

    def start(self):
        self.conn_key = self.bm.start_multiplex_socket(['audiousdt@kline_1m', 'bnbusdt@kline_1m', 'grtusdt@kline_1m',  'btcusdt@kline_1m'], self.process_message)
        self.conn_mt_key = self.bm.start_multiplex_socket(['audiousdt@miniTicker', 'bnbusdt@miniTicker', 'grtusdt@miniTicker', 'btcusdt@miniTicker'], self.process_miniticker)
        # self.conn_key = self.bm.start_kline_socket('AUDIOUSDT', self.process_message, interval=KLINE_INTERVAL_1MINUTE)
        # self.conn_key = self.bm.start_aggtrade_socket('BNBBTC', self.process_message)
        self.bm.start()

    def stop(self):
        self.bm.stop_socket(self.conn_key)
        self.bm.stop_socket(self.conn_mt_key)