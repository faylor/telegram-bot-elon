import cryptowatch as cw
from google.protobuf.json_format import MessageToJson
import os
import json
import asyncio

import requests
from bot.settings import (TELEGRAM_BOT)



class Crytream():

    def __init__(self) -> None:
        self.chat_ids = []
        cw.api_key = os.environ["CRYPTOWATCH_API"]
        cw.stream.subscriptions = ["assets:60:book:snapshots"]
        # cw.stream.on_trades_update = self.handle_trades_update
        self.bot = None
        self.volumes = []
        self.last_average = 0
        self.volume_count = 0
        self.sell_updates = 0
        self.buy_updates = 0
    
    def handle_orderbook_snapshot_updates(self, orderbook_snapshot_update):
        
        last_message = json.loads(MessageToJson(orderbook_snapshot_update))
        order_book = last_message["marketUpdate"]["orderBookUpdate"]
        if "bids" in order_book and "asks" in order_book:
            bids = ["bids"]
            asks = last_message["marketUpdate"]["orderBookUpdate"]["asks"]

            buy_pressure = len(bids) / len(asks)
            if buy_pressure < 0.0001 and self.sell_updates == 0:
                bot_key = TELEGRAM_BOT
                chat_id = self.chat_ids[0]
                text = "SELL PRESSURE: " + str(float(buy_pressure))
                send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                resp = requests.post(send_message_url)
                self.sell_updates = self.buy_updates + 1
                self.buy_updates = 0
            if buy_pressure > 10 and self.buy_updates == 0:
                bot_key = TELEGRAM_BOT
                chat_id = self.chat_ids[0]
                text = "BUY PRESSURE: " + str(float(buy_pressure))
                send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                resp = requests.post(send_message_url)
                self.buy_updates = self.sell_updates + 1
                self.sell_updates = 0
            if self.buy_updates + self.sell_updates > 4:
                self.stop()
                text = "Stopped after 10 switches"
                send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                resp = requests.post(send_message_url)


    def handle_intervals_update(self, interval_update):
        last_message = json.loads(MessageToJson(interval_update))
        intervals = last_message["marketUpdate"]["intervalsUpdate"]["intervals"]

        for interval in intervals:
            if interval["periodName"] == "60":
                last_volume = float(interval["volumeBaseStr"])

        if self.last_average > 0 and self.volume_count > 50:
            if (self.last_average * 50) < last_volume:
                bot_key = TELEGRAM_BOT
                chat_id = self.chat_ids[0]
                text = "ALERT SPIKE IN BTC VOLUME:\nLATEST:" + str(int(last_volume)) + "\nAVERAGE:" + str(int(self.last_average))
                send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                resp = requests.post(send_message_url)
        
        self.last_average = ((self.last_average * self.volume_count) + last_volume)/(self.volume_count + 1)
        self.volume_count = self.volume_count + 1

    
    def add_chat_id(self, chat_id):
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)

    def remove_chat_id(self, chat_id):
        if chat_id in self.chat_ids:
            self.chat_ids.remove(chat_id)

    def start(self, bot):
        self.bot = bot
  

        cw.stream.on_orderbook_snapshot_update = self.handle_orderbook_snapshot_updates


        # cw.stream.on_intervals_update = self.handle_intervals_update
        cw.stream.connect()

    def stop(self):
        cw.stream.disconnect()