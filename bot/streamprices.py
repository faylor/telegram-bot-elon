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
        cw.stream.subscriptions = ["assets:60:ohlc"]
        # cw.stream.on_trades_update = self.handle_trades_update
        self.bot = None
        self.volumes = []
        self.last_average = 0
        self.volume_count = 0
    

    def handle_intervals_update(self, interval_update):
        # market_msg = ">>> Market#{} Exchange#{} Pair#{}: {} New Trades".format(
        #     trade_update.marketUpdate.market.marketId,
        #     trade_update.marketUpdate.market.exchangeId,
        #     trade_update.marketUpdate.market.currencyPairId,
        #     len(trade_update.marketUpdate.tradesUpdate.trades),
        # )
        # print(market_msg)
        #         {
        #   "marketUpdate": {
        #     "intervalsUpdate": {
        #       "intervals": [
        #         {
        #           "closetime": "1616142540",
        #           "ohlc": {
        #             "openStr": "54121.8",
        #             "highStr": "54161",
        #             "lowStr": "54121.6",
        #             "closeStr": "54160.5"
        #           },
        #           "volumeBaseStr": "0.11336775",
        #           "volumeQuoteStr": "6139.861519969",
        #           "periodName": "60"
        #         }
        #       ]
        #     },
        #     "market": {
        #       "exchangeId": "4",
        #       "currencyPairId": "5284",
        #       "marketId": "61496"
        #     }
        #   }
        # }
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

        cw.stream.on_intervals_update = self.handle_intervals_update
        cw.stream.connect()

    def stop(self):
        cw.stream.disconnect()