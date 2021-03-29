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
           
    def process_message(self, msg):
        try:
            taker_buy_vol = msg["k"]["Q"]
            data = r.get(COIN_DATA_KEY.format("AUDIO"))
            if data is not None:
                js = json.loads(data.decode("utf-8"))
                if "Q" in js:
                    if js["Q"] is None:
                        js = {"Q": [taker_buy_vol]}
                    else:
                        if len(js["Q"]) > 3:
                            last_VOL = js["Q"][-1]
                            diff = 100 * (taker_buy_vol - last_VOL)/last_VOL
                            if abs(diff) > 1:
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
        self.conn_key = self.bm.start_kline_socket('AUDIOUSDT', self.process_message, interval=KLINE_INTERVAL_3MINUTE)
        # self.conn_key = self.bm.start_aggtrade_socket('BNBBTC', self.process_message)
        self.bm.start()

    def stop(self):
        self.bm.stop_socket(self.conn_key)