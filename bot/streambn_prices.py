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
        self.green_count = {}
        self.red_count = {}
        self.velocity = {}
        self.velocity_previous = {}
           
    def process_message(self, msg):
        try:
            stream, data = msg['stream'], msg['data']
            taker_buy_vol = float(data["k"]["Q"])
            is_end = data["k"]["x"]
            if is_end == True:
                logging.error("HERE")
                open_price = float(data["k"]["o"])
                close_price = float(data["k"]["c"])
                if stream in self.velocity:
                    self.velocity_previous[stream] = self.velocity[stream]
                self.velocity[stream] = (close_price - open_price)/1 # 1min
                logging.error("HERE3")
                
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
                logging.error("HERE2")
                
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
                                    text = "AUDIO RAPID CHANGE " + str(round(float(diff),1)) + "%"
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
                logging.error("HERE1")
                
                bot_key = TELEGRAM_BOT
                chat_id = self.chat_ids[0]
                text = str(stream) + " GREENS: " + str(self.green_count[stream]) + " POSSIBLE PUMP: " + str(round(float(taker_buy_vol),1)) + "Vol" + str(self.velocity[stream]) + " - " + str(self.velocity_previous[stream])
                send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                resp = requests.post(send_message_url)
                self.green_count = 0
            elif stream in self.red_count and self.red_count[stream] > 1 and self.velocity[stream] < self.velocity_previous[stream]:
                bot_key = TELEGRAM_BOT
                chat_id = self.chat_ids[0]
                text = str(stream) + " RED: " + str(self.red_count[stream]) + " POSSIBLE DUMP: " + str(round(float(taker_buy_vol),1)) + "Vol" + str(self.velocity[stream]) + " - " + str(self.velocity_previous[stream])
                send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                resp = requests.post(send_message_url)
                self.red_count = 0
        except Exception as e:
            logging.error("BN Stream process error:" + str(e))
        # do something

    # def handle_intervals_update(self, interval_update):
    #     klines = client.get_historical_klines("BNBBTC", Client.KLINE_INTERVAL_1MINUTE, "1 day ago UTC")

   
    def add_chat_id(self, chat_id):
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)

    def remove_chat_id(self, chat_id):
        if chat_id in self.chat_ids:
            self.chat_ids.remove(chat_id)

    def start(self):
        self.conn_key = self.bm.start_multiplex_socket(['audiousdt@kline_1m', 'btcusdt@kline_1m'], self.process_message)
        # self.conn_key = self.bm.start_kline_socket('AUDIOUSDT', self.process_message, interval=KLINE_INTERVAL_1MINUTE)
        # self.conn_key = self.bm.start_aggtrade_socket('BNBBTC', self.process_message)
        self.bm.start()

    def stop(self):
        self.bm.stop_socket(self.conn_key)