import cryptowatch as cw
from google.protobuf.json_format import MessageToJson
import os
import json
import asyncio

import requests
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
        self.store_data()
        logging.error("STOP STORING")
        self.timer = None

    def store_data(self):
        data = get_simple_price_gecko("btc")
        logging.error("GOT PRICES:" + json.dumps(data))
        
        r.save(COIN_DATA_KEY.format("btc"), data)
        self.stored = self.stored + 1
        logging.error("STORED:" + str(self.stored))

    
        
        
