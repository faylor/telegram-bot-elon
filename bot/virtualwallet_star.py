from binance.client import Client
from .settings import TELEGRAM_BOT
import time
import logging
import json
import requests
import asyncio
import datetime
from dateutil import parser
import time
from .bot import r


SCORE_KEY = "{chat_id}_bagscore_{user_id}"
STAR_KEY = "{chat_id}_star_{user_id}"
PRICES_IN = "USDT"

class StarCard():

    def __init__(self, chat_id, user_id, delay):
        self.chat_id = chat_id
        self.user_id = user_id
        self.delay = delay

    def update(self):
        key = STAR_KEY.format(chat_id=str(self.chat_id), user_id=str(self.user_id))
        save = r.get(key)
        if save is not None:
            js = json.loads(save.decode("utf-8"))
            end_time = parser.parse(js["end_time"])
            live, free, _ = self.get_user_bag_score()
            start_total = js["start_total"]
            current_result = 2 * ((live + free) - start_total)
            if datetime.datetime.now() >= end_time:
                r.delete(key)
                key = SCORE_KEY.format(chat_id=str(self.chat_id), user_id=str(self.user_id))
                save = r.get(key) 
                if save is not None:
                    js = json.loads(save.decode("utf-8"))
                    if PRICES_IN.lower() in js:
                        current_amount = float(js[PRICES_IN.lower()])
                        js[PRICES_IN.lower()] = current_result + current_amount
                        r.set(key, json.dumps(js))
                        self.send_chat_message(text="STAR ENDED! Final Star Bonus = ${current_result}")
                self.send_chat_message(text="STAR ENDED! Couldn't find user score??")
                raise asyncio.CancelledError()
            else:
                self.send_chat_message(text=f"STAR RUNNING! Current Star Bonus = ${current_result}")
    
    def get_user_bag_score(self):
        try:
            key =  SCORE_KEY.format(chat_id=str(self.chat_id), user_id=self.user_id)
            js = r.get(key)
            if js is not None:
                js = js.decode('utf-8')
                js = json.loads(js)
                return float(js["live"]), float(js[PRICES_IN.lower()]), int(js["trades"])
            else:
                if PRICES_IN.lower() == "btc":
                    amount = 1
                else:
                    amount = 1000
                js = {"live": 0, PRICES_IN.lower(): amount, "trades": 0}
                r.set(key, json.dumps(js))
                return 0, amount, 0
        except Exception as e:
            logging.error("FAILED to save user score for bag:" + str(e))

    def send_chat_message(self, text):
        try:
            bot_key = TELEGRAM_BOT
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={self.chat_id}&text={text}&parse_mode=HTML'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Failed to send chat message:" + str(e))
