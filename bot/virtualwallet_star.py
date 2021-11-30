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
from .prices import get_price, get_simple_price_gecko, get_simple_prices_gecko, coin_price, round_sense, coin_price_realtime, get_bn_price


SCORE_KEY = "{chat_id}_bagscore_{user_id}"
STAR_KEY = "{chat_id}_star_{user_id}"
PRICES_IN = "USDT"

def update_open_stars(chat_id):
    chat_id = str(chat_id)
    score_key = STAR_KEY.format(chat_id=chat_id, user_id="*")
    saves = r.scan_iter(score_key)
    open_user_id = []
    for key in saves:
        logging.error("Here:")
        key = key.decode('utf-8')
        value = r.get(key)
        logging.error("value:" + value)
        if value is not None:
            value = value.decode('utf-8')
            user_id = key.replace(chat_id + "_star_", "")
            star_card = StarCard(chat_id=chat_id, user_id=user_id)
            star_card.update()
            open_user_id.append(star_card)
    return open_user_id
            

class StarCard():

    def __init__(self, chat_id, user_id):
        self.chat_id = str(chat_id)
        self.user_id = str(user_id)

    def init_star(self, hours):
        key = STAR_KEY.format(chat_id=self.chat_id, user_id=self.user_id)
        dt = datetime.datetime.now() + datetime.timedelta(hours=hours)
        live = self.get_users_total_value()
        js = {"end_time": dt.isoformat(), "start_total": live}
        r.set(key, json.dumps(js))
        self.send_chat_message(text=f"STAR STARTING! Ends at {dt.isoformat()} - start value ${live}")

    def update(self):
        key = STAR_KEY.format(chat_id=str(self.chat_id), user_id=str(self.user_id))
        save = r.get(key)
        if save is not None:
            js = json.loads(save.decode("utf-8"))
            end_time = parser.parse(js["end_time"])
            live = self.get_users_total_value()
            start_total = js["start_total"]
            current_result = 2 * (live - start_total)
            if datetime.datetime.now() >= end_time:
                self.send_chat_message(text="Deleting star... (Debug only)")
                r.delete(key)
                key = SCORE_KEY.format(chat_id=str(self.chat_id), user_id=str(self.user_id))
                save = r.get(key) 
                if save is not None:
                    js = json.loads(save.decode("utf-8"))
                    if PRICES_IN.lower() in js:
                        current_amount = float(js[PRICES_IN.lower()])
                        js[PRICES_IN.lower()] = current_result + current_amount
                        r.set(key, json.dumps(js))
                        self.send_chat_message(text=f"STAR ENDED! Final Star Bonus = ${current_result}")
                        raise asyncio.CancelledError()
                self.send_chat_message(text="STAR ENDED! Couldn't find user score??")
                raise asyncio.CancelledError()
            else:
                self.send_chat_message(text=f"STAR RUNNING! Current Star Bonus = ${current_result}")
    
    def get_users_total_value(self):
        try:
            saves = r.scan_iter("At_" + self.chat_id + "_*_" + self.user_id)

            symbols = []
            keys = []
            for key in saves:
                symbols.append(key.decode('utf-8').replace("At_" + self.chat_id + "_" , "").replace("_" + self.user_id,""))
                keys.append(key.decode('utf-8'))
            
            try:
                coin_prices = None
                coin_prices = coin_price_realtime(symbols, PRICES_IN)
            except:
                logging.error("FAILED TO GET COIN PRICES")

            total_value = float(0.00)
            i = 0
            for key in keys:
                symbol = symbols[i]

                if coin_prices is not None and symbol.upper() in coin_prices:
                    p = coin_prices[symbol.upper()]["quote"][PRICES_IN]["price"]
                else:
                    p = get_bn_price(symbol, PRICES_IN)
                if float(p) > 0:
                    value = r.get(key)
                    if value is not None:
                        value = value.decode('utf-8')
                        if "{" in value:
                            js = json.loads(value)
                            coins = float(js["coins"])
                        else:
                            coins = 1
                        total_value = total_value + (coins * p)
                i = i + 1
            
            key =  SCORE_KEY.format(chat_id=self.chat_id, user_id=self.user_id)
            js = r.get(key)
            if js is not None:
                js = js.decode('utf-8')
                js = json.loads(js)
                val_side = float(js[PRICES_IN.lower()])
            else:
                val_side = 0

            return round(total_value + val_side, 2)
        except Exception as e:
            logging.warn("Couldnt get live values data:" + str(e))
            return 0


    def get_user_bag_score(chat_id, user_id):
        try:
            key =  SCORE_KEY.format(chat_id=str(chat_id), user_id=user_id)
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
