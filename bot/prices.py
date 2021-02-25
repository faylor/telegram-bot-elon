import logging
import requests
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects

import os
from aiogram import types
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

retry_strategy = Retry(
    total=1,
    status_forcelist=[500, 502, 503, 504],
    method_whitelist=["HEAD", "GET", "OPTIONS"],
    backoff_factor=1
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

def to_zero(js, key1, key2, key3):
    try:
        r = js[key1][key2][key3]
        if r is None:
            r = 0
        return r
    except Exception as e:
        return 0

def get_price_extended(label):
    http.headers.update({"x-messari-api-key": os.environ["MESSARI_API_KEY"]})
    price, change_1hr, change_24hr = 0, 0, 0
    try:
        url = "https://data.messari.io/api/v1/assets/" + label + "/metrics"
        resp = http.get(url, timeout=(1, 1))
        if resp.status_code == 200:
            js = resp.json()
            change_1hr = to_zero(js, "data", "market_data", "percent_change_usd_last_1_hour")
            change_24hr = to_zero(js, "data", "market_data", "percent_change_usd_last_24_hours")
            change_btc_1hr = to_zero(js, "data", "market_data", "percent_change_btc_last_1_hour")
            change_btc_24hr = to_zero(js, "data", "market_data", "percent_change_btc_last_24_hours")
            days_since_alt = to_zero(js, "data", "all_time_high", "days_since")
            down_from_alt = to_zero(js, "data", "all_time_high", "percent_down")
        else:
            logging.error("Response Failed..." + str(resp.status_code))
            logging.error("Response Test..." + str(resp.text))
            return 0,0,0,0,0,0
    except Exception as e:
        logging.error(e)
        return 0,0,0,0,0,0
    return change_1hr, change_24hr, change_btc_1hr, change_btc_24hr, days_since_alt, down_from_alt

def get_price(label):
    price, change_1hr, change_24hr = 0, 0, 0
    try:
        url = "https://data.messari.io/api/v1/assets/" + label + "/metrics"
        resp = http.get(url, timeout=(1, 1))
        if resp.status_code == 200:
            js = resp.json()
            price = js["data"]["market_data"]["price_usd"]
            price_btc = js["data"]["market_data"]["price_btc"]
            change_1hr = js["data"]["market_data"]["percent_change_usd_last_1_hour"]
            change_24hr = js["data"]["market_data"]["percent_change_usd_last_24_hours"]
        else:
            logging.error("Response Failed..." + str(resp.status_code))
            logging.error("Response Test..." + str(resp.text))
            return 0,0,0,0
    except Exception as e:
        logging.error(e)
        return 0, 0, 0, 0
    if price is None:
        price = 0
    if change_1hr is None:
        change_1hr = 0
    if change_24hr is None:
        change_24hr = 0
    if price_btc is None:
        price_btc = 0
    return price, change_1hr, change_24hr, price_btc

def coin_price(labels):
    http.headers.update({"X-CMC_PRO_API_KEY": os.environ["COIN_API"]})
    s = ",".join(labels)
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    parameters = {
        'symbol':s,
        'skip_invalid': True
    }

    try:
        response = http.get(url, params=parameters)
        if response.status_code == 429:
            # use mess
            logging.error("HIT LIMIT")
        else:
            coins = {}
            data = response.json()
            data_arr = data["data"]
            return data_arr

#         "USD": {
#             "price": 6602.60701122,
#             "volume_24h": 4314444687.5194,
#             "percent_change_1h": 0.988615,
#             "percent_change_24h": 4.37185,
#             "percent_change_7d": -12.1352,
#             "percent_change_30d": -12.1352,
#             "market_cap": 113563929433.21645,
#             "last_updated": "2018-08-09T21:56:28.000Z"

        
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)


def get_news(label):
    try:
        url = "https://data.messari.io/api/v1/news/" + label
        resp = http.get(url, timeout=(1, 1))
        if resp.status_code == 200:
            js = resp.json()
            news_array = js["data"]
            if len(news_array) > 0:
                article = js["data"][0]
                title = article["title"]
                content = article["content"]
                return title, content
        else:
            logging.error("Response Failed..." + str(resp.status_code))
            logging.error("Response Test..." + str(resp.text))
            return "Not Available", ""
    except Exception as e:
        logging.error(e)
        return "Not Available", ""


def round_sense(price):
    if price is None:
        return 0
    if price > 100:
        return int(price)
    if price > 10:
        return round(price, 1)
    if price > 1:
        return round(price, 2)
    return round(price, 4)


def get_change_label(c, lpad=None):
    label_on_change = "🔻"
    if c > 3:
        label_on_change = "🚀"
    elif c > 0:
        label_on_change = "↗️"
    elif c == 0:
        label_on_change = "  "
    elif c > -3:
        label_on_change = "↘️"
    if lpad is not None:
        return label_on_change + str(round(c,1)).replace("-","").ljust(lpad, ' ')
    return label_on_change + str(round(c,1)).replace("-","")


def get_abs_difference(s, p):
    estimate = -999999
    try:
        if s != "NONE":
            if "k" in s.lower():
                tmp_a = s.lower().replace("k","")
                tmp_a_double = float(tmp_a)
                estimate = tmp_a_double * 1000
            else:
                estimate = float(str(s))
        return abs(estimate - p)
    except Exception as e:
        logging.warn("Cannot convert abs difference:" + str(e))
        return -999999


