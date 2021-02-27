import logging
import requests
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
from datetime import datetime
import os
from aiogram import types
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import redis

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

from .settings import (REDIS_URL)
r = redis.from_url(REDIS_URL)

def to_zero(js, key1, key2, key3):
    try:
        r = js[key1][key2][key3]
        if r is None:
            r = 0
        return r
    except Exception as e:
        return 0

def to_zero_2(js, key1, key2):
    try:
        r = js[key1][key2]
        if r is None:
            r = 0
        return r
    except Exception as e:
        return 0

def get_rapids():
    http.headers.clear()
    try:
        url = "https://api.cryptometer.io/rapid-movements"
        parameters = {
            'api_key': os.environ["METER_IO_API"]
        }
        response = http.get(url, params=parameters)
        if response.status_code == 429:
            # use mess
            logging.error("HIT LIMIT")
        else:
            coins = {}
            data = response.json()
            data_arr = data["data"]
            #  "data":[
            #     {
            #        "pair":"WLO-USD",
            #        "exchange":"bitfinex",
            #        "change_detected":5.17,
            #        "side":"PUMP",
            #        "timestamp":"2019-12-11T11:18:15.000Z"
            #     }
            #  ]
            return data_arr
    except Exception as e:
        logging.error(e)
        return 0,0,0,0,0,0
    return None


def load_ath_data():
    try:
        data = r.get("ATH_cryptorank")
        if data is not None:
            logging.info("USING ATH CACHE")
            return data
        logging.info("GETTING NEW ATH DATA")
        url = "https://api.cryptorank.io/v0/coins?locale=en"
        http.headers.clear()
        resp = http.get(url)
        if resp.status_code == 200:
            js = resp.json()
            data = js["data"]
            r.set("ATH_cryptorank", data, ex=60)
        else:
            logging.error("Response Failed..." + str(resp.status_code))
            logging.error("Response Test..." + str(resp.text))
            data = []
        return data
    except Exception as e:
        logging.error(e)
        return []

def search_data(dic, symbols):
    ''' Define your own condition here'''
    return dic['symbol'].lower() in symbols

def get_filtered_cr_data(labels):
    try:
        data = r.get("ATH_cr_" + labels)
        if data is not None:
            logging.info("USING ATH CR FILTERED CACHE")
            return data

        logging.info("GETTING NEW CR FILTERED DATA")
        data = load_ath_data()
        if data is not None:
            filtered_data = [d for d in data if search_data(d, labels)]
            results = {}
            for f in filtered_data:
                results[f["symbol"]] = f
            r.set("ATH_cr_" + labels, results, ex=60)
            return results
        else:
            logging.error("Filtered Failed... No Data")
            return None
    except Exception as e:
        logging.error(e)
        return None

def get_ath_ranks(labels):
    try:
        data_cr = get_filtered_cr_data(labels)
        data_cmc = coin_price(labels)
        results = {}
        if data_cr is None and data_cmc is None:
            logging.error("ATH Ranks: No data from cr or cmc")
            return None
        for l in labels:
            results[l] = format_price_extended(data_cr[l], data_cmc[l])
        return results
    except Exception as e:
        logging.error(e)
        return None

def format_price_extended(data_cr, data_cmc):
    try:
        coin_result = {}
        price = to_zero_2(data_cr, "price", "USD")
        coin_result["change_usd_1hr"] = to_zero(data_cmc, "quote", "usd", "percent_change_1h")
        # TODO no data for btc 1hr
        coin_result["change_btc_1hr"] = coin_result["change_usd_1hr"] 
        change_usd_hr = to_zero(data_cr, "histPrices", "24H", "USD")
        coin_result["change_usd_24hr"] = to_zero(data_cmc, "quote", "usd", "percent_change_24h")
        if coin_result["change_usd_24hr"] == 0:
            coin_result["change_usd_24hr"] = 100*(price - change_usd_hr)/change_usd_hr
        change_btc_hr = to_zero(data_cr, "histPrices", "24H", "BTC")
        coin_result["change_btc_24hr"] = 100*(price - change_btc_hr)/change_btc_hr
        date_of_string = data_cr["athPrice"]["date"]
        date_object = datetime.strptime(date_of_string, "%Y-%m-%d").date()
        days_since = datetime.utcnow().date() - date_object
        coin_result["days_since_ath"] = days_since.days
        ath = to_zero_2(data_cr, "athPrice", "USD")
        
        if ath > price:
            coin_result["down_from_alt"] = -100 * (price - ath) / ath
        else: 
            coin_result["down_from_alt"] = 0
        return coin_result
    except Exception as e:
        logging.error(e)
    return {}
    
def get_price_extended(label):
    http.headers.clear()
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
    try:
        data = r.get("QUOTES_cmc_" + labels)
        if data is not None:
            logging.info("USING ATH CACHE")
            return data
        logging.info("GETTING NEW ATH DATA")
        http.headers.clear()
        http.headers.update({"X-CMC_PRO_API_KEY": os.environ["COIN_API"]})
        s = ",".join(labels)
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        parameters = {
            'symbol':s,
            'skip_invalid': True
        }
        response = http.get(url, params=parameters)
        if response.status_code == 429:
            logging.error("HIT LIMIT")
        else:
            coins = {}
            data = response.json()
            data_arr = data["data"]
            r.set("QUOTES_cmc_" + labels, data_arr, ex=60)
            return data_arr
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        logging.error("COIN_PRICE Error: " + str(e))

def get_last_trades(x):
    http.headers.clear()
    url = 'https://api.cryptowat.ch/markets/binance/btcusdt/trades'
    parameters = {
        'limit': x
    }

    try:
        response = http.get(url, params=parameters)
        if response.status_code == 429:
            # use mess
            logging.error("HIT LIMIT")
        else:
            coins = {}
            data = response.json()
            data_arr = data["result"]
            return data_arr
    
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)

def get_ohcl_trades(coin):
    http.headers.clear()
    url = 'https://api.cryptowat.ch/markets/binance/' + coin + 'usdt/ohlc?periods=60'
# https://bittrex.com/Api/v2.0/pub/market/GetTicks?marketName=USDT-BTC&tickInterval=fiveMin
    try:
        response = http.get(url)
        if response.status_code == 429:
            # use mess
            logging.error("HIT LIMIT")
        else:
            coins = {}
            data = response.json()
            data_arr = data["result"]["60"]
            return data_arr
    
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


