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
def fire_and_forget(f):
    def wrapped(*args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(None, f, *args, *kwargs)
    return wrapped

class DataWatcher():

    def __init__(self):
        self.stored = 0
        self.timer = 60
        
    @fire_and_forget
    def start(self, timer=60):
        self.timer = timer
        while self.timer is not None:
            logging.error("CALLING STORE_DATA")
            self.store_data()
            asyncio.sleep(self.timer)
    
    def stop(self):
        self.store_data()
        logging.error("STOP STORING")
        self.timer = None

    def store_data(self):
        data = get_simple_price_gecko("btc")
        logging.error("GOT PRICES:" + json.dumps(data))
        
        r.set(COIN_DATA_KEY.format("btc"), json.dumps(data))
        self.stored = self.stored + 1
        logging.error("STORED:" + str(self.stored))

    
        
        
