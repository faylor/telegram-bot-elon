import os
import json
import asyncio

import requests
from bot.settings import (BN_API_KEY, BN_API_SECRET)
from binance.websockets import BinanceSocketManager
from binance.client import Client

class Bntream():

    def __init__(self) -> None:
        self.chat_ids = []
        self.client = Client(BN_API_KEY, BN_API_SECRET)
        self.bm = BinanceSocketManager(self.client)
        self.volumes = []
        self.last_average = 0
        self.volume_count = 0
        self.sell_updates = 0
        self.buy_updates = 0
           
    def process_message(self, msg):
        print("message type: {}".format(msg['e']))
        print(msg)
        text = "BN Message: " + json.dumps(msg)
        send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
        resp = requests.post(send_message_url)
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
        self.bm.start_aggtrade_socket('BNBBTC', self.process_message)
        self.bm.start()

    def stop(self):
        self.bm.stop()