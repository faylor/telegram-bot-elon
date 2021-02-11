import logging
import requests
from aiogram import types
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    method_whitelist=["HEAD", "GET", "OPTIONS"],
    backoff_factor=2
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

def get_price(label):
    price, change_1hr, change_24hr = 0, 0, 0
    try:
        url = "https://data.messari.io/api/v1/assets/" + label + "/metrics"
        resp = http.get(url)
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


def weekly_tally(message: types.Message, r):
    p_btc, _, _, _ = get_price("btc")
    p_eth, _, _, _ = get_price("eth")
    out = "BTC Bets (Current=" + str(round(p_btc,0)) + "):\n"
    winning = ""
    winning_diff = 99999
    cid = str(message.chat.id)
    for key in r.scan_iter(f"{cid}_BTC_*"):
        a = r.get(key).decode('utf-8') or "NONE"
        d = get_abs_difference(a, p_btc)
        name = str(key.decode('utf-8')).replace(f"{cid}_BTC_","")
        if d <= winning_diff:
            if d == winning_diff:
                winning = winning + ", " + name
            else:
                winning = name
                winning_diff = d
        out = out + name + " => " + a + "  -- DIFF = " + str(round(d,1)) + "\n"
    out = out + "\n LOOK WHO IS WINNING BTC == " + winning + "\n"
    out = out + "\nETH Bets (Current=" + str(round(p_eth,0)) + "):\n"
    winning_eth = ""
    winning_diff = 99999
    for key in r.scan_iter(f"{cid}_ETH_*"):
        a = r.get(key).decode('utf-8') or "NONE"
        d = get_abs_difference(a, p_eth)
        name = str(key.decode('utf-8')).replace(f"{cid}_ETH_","")
        if d <= winning_diff:
            if d == winning_diff:
                winning_eth = winning_eth + ", " + name
            else:
                winning_eth = name
                winning_diff = d
        out = out + name + " => " + a + "  -- DIFF = " + str(round(d,1)) + "\n"
    out = out + "\n LOOK WHO IS WINNING ETH == " + winning_eth + "\n"
    return out, winning, winning_eth