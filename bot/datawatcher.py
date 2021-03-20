import cryptowatch as cw
from google.protobuf.json_format import MessageToJson
import os
import json
import asyncio

import requests
import asyncio
improt json
import logging
from .prices import get_simple_price_gecko
import redis
from .settings import (REDIS_URL)
r = redis.from_url(REDIS_URL)

COIN_DATA_KEY = "DATA_{}"

class DataWatcher():

    def __init__(self):
        self.stored = 0
        
    async def start(self, timer=30):
        self.store_data()
        logging.error("CALLED STORING")
        await asyncio.sleep(timer)

    async def store_data(self):
        data = get_simple_price_gecko("btc")
        logging.error("GOT PRICES:" + json.dumps(data))
        
        r.save(COIN_DATA_KEY.format("btc"), data)
        self.stored = self.stored + 1
        logging.error("STORED:" + str(self.stored))

    
        
        
