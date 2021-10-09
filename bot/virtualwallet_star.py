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
from .virtualwallet import get_user_bag_score, STAR_KEY, SCORE_KEY, PRICES_IN


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
            live, free, _ = get_user_bag_score(self.chat_id, self.user_id)
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
    
    def send_chat_message(self, text):
        try:
            bot_key = TELEGRAM_BOT
            send_message_url = f'https://api.telegram.org/bot{bot_key}/sendMessage?chat_id={self.chat_id}&text={text}&parse_mode=HTML'
            resp = requests.post(send_message_url)
        except Exception as e:
            logging.error("Failed to send chat message:" + str(e))
