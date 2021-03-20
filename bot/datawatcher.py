from google.protobuf.json_format import MessageToJson
import os
import json
import asyncio
import requests
from bot.settings import (TELEGRAM_BOT)
import asyncio
import json
import logging
from .prices import get_simple_price_gecko
import redis
from .settings import (REDIS_URL)
r = redis.from_url(REDIS_URL)

COIN_DATA_KEY = "DATA_{}"

class DataWatcher():

    def __init__(self):
        self.stored = 0
        self.timer = 60
        
    async def start(self, timer=60):
        self.timer = timer
        while self.timer is not None:
            logging.error("CALLING STORE_DATA")
            self.store_data()
            await asyncio.sleep(self.timer)
    
    def stop(self):
        logging.error("STOP STORING")
        self.timer = None

    def store_data(self):
        price_data = get_simple_price_gecko("btc")
        logging.error("GOT PRICES:" + json.dumps(price_data))
        data = r.get(COIN_DATA_KEY.format("btc"))
        if data is not None:
            js = json.loads(data.decode("utf-8"))
            if "p" in js:
                last_price = js["p"][-1]
                diff = price_data["btc"]["usd"] - last_price
                bot_key = TELEGRAM_BOT
                chat_id = self.chat_ids[0]
                text = "DIFF PRESSURE: " + str(float(diff))
                send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={chat_id}&text={text}'
                resp = requests.post(send_message_url)
                js["p"] = js["p"].append(price_data["btc"]["usd"]) 
            else:
                js["p"] = [price_data["btc"]["usd"]]
        else:
            js = {"p": [price_data["btc"]["usd"]]}
        logging.error("JS:" + json.dumps(js))
        r.set(COIN_DATA_KEY.format("btc"), json.dumps(js))
        self.stored = self.stored + 1
        logging.error("STORED:" + str(self.stored))

    
        
        
