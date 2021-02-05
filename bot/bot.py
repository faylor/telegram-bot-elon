import logging
import requests
import json
from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher, filters
from aiogram.utils.executor import start_webhook
from aiogram.utils.markdown import escape_md
from bot.settings import (TELEGRAM_BOT, HEROKU_APP_NAME,
                          WEBHOOK_URL, WEBHOOK_PATH,
                          WEBAPP_HOST, WEBAPP_PORT, REDIS_URL)
import redis

r = redis.from_url(REDIS_URL)

bot = Bot(token=TELEGRAM_BOT)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())


def getUrl(animal):
    contents = requests.get('https://api.the' + animal + 'api.com/v1/images/search')
    js = contents.json()
    print(js)
    url = js[0]["url"]
    return url

@dp.message_handler(commands=['doge', 'dog'])
async def sendDogImage(message: types.Message):
    url = getUrl('dog')
    await bot.send_photo(chat_id=message.chat.id, photo=url)

@dp.message_handler(commands=['cate', 'cat'])
async def sendCatImage(message: types.Message):
    url = getUrl('cat')
    await bot.send_photo(chat_id=message.chat.id, photo=url)

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['red([a-zA-Z]*)']))
async def send_red(message: types.Message, regexp_command):
    await bot.send_sticker(chat_id=message.chat.id, sticker="https://tenor.com/view/spacex-fail-landing-explosion-explode-gif-19509668")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['jelly([\sa-zA-Z]*)']))
async def send_green(message: types.Message, regexp_command):
    name = regexp_command.group(1)
    await message.reply(f'Hello {name}, you have Jelly Hands. Love Elon. Kisses.')
    await bot.send_sticker(chat_id=message.chat.id, sticker="https://tenor.com/view/laughing-spacex-elon-musk-elon-musk-gif-13597458")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['green([a-zA-Z]*)']))
async def send_green(message: types.Message, regexp_command):
    await bot.send_sticker(chat_id=message.chat.id, sticker="https://tenor.com/view/spacex-bitcoin-rd_btc-elon-musk-elon-gif-20158067")

@dp.message_handler(commands=['elon', 'Elon', 'elon?', 'Elon?', 'help'])
async def send_help(message: types.Message):
    await message.reply(f'SUP! {message.from_user.first_name}? \n Get Price: /$btc /$aave ..etc \n Show Table: /lambo /prices \n bet: /bet btc 12.3k eth 1.2k\n and /bets. \n Fun: /jelly /jellyhand')

@dp.message_handler(commands=['prices', 'btc', 'lambo', 'whenlambo', 'lambos', 'whenlambos', 'price', '$', '£', '€'])
async def prices(message: types.Message):
    chat_id = message.chat.id
    mains = ["BTC", "ETH", "GRT", "LTC", "ADA", "AAVE", "DOGE", "ZIL"]
    out = "<pre>| Symbol|  Price      | +/- 1hr  |\n"
    totes = 0
    for l in mains:
        p, c, _ = get_price(l)
        totes = totes + c
        l = l.ljust(5, ' ')
        label_on_change = "   "
        if c > 3:
            label_on_change = "++++"
        elif c > 2:
            label_on_change = "  ++"
        elif c > 0:
            label_on_change = "   +"
        price = str(round(p,4)).ljust(10,' ')
        change = label_on_change + str(round(c,1)).ljust(5,' ')
        out = out + f"| {l} | ${price} | {change} | \n"
    if totes < 0:
        out = out + "</pre>OUCH, NO LAMBO FOR YOU!" 
    elif totes > 15:
        out = out + "</pre>OK OK, LAMBO FOR YOU!"
    else:
        out = out + "</pre>MEH, MAYBE LAMBO. HODL."
    await bot.send_message(chat_id=chat_id, text=out, parse_mode="HTML")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['\$([a-zA-Z]*)']))
async def send_welcome(message: types.Message, regexp_command):
    item = regexp_command.group(1)
    p, c, c24 = get_price(item)
    await bot.send_message(chat_id=message.chat.id, text=f"{item} = ${round(p,4)}  Last hr = {round(c,2)}%, Last 24hr = {round(c24,2)}%")

def get_price(label):
    price, change_1hr, change_24hr = 0, 0, 0
    try:
        url = "https://data.messari.io/api/v1/assets/" + label + "/metrics"
        resp = requests.get(url)
        js = resp.json()
        price = js["data"]["market_data"]["price_usd"]
        change_1hr = js["data"]["market_data"]["percent_change_usd_last_1_hour"]
        change_24hr = js["data"]["market_data"]["percent_change_usd_last_24_hours"]
    except Exception as e:
        logging.error(e)
    return price, change_1hr, change_24hr

@dp.message_handler(commands=['bets delete', 'weekly delete', 'weeklybets delete', '#weeklybets delete'])
async def finish_weekly(message: types.Message):
    for key in r.scan_iter("BTC_*"):
        r.delete(key)
    for key in r.scan_iter("ETH_*"):
        r.delete(key)
    await bot.send_message(chat_id=message.chat.id, text="DELETED BETS. Good Luck.")

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

@dp.message_handler(commands=['bets', 'weekly', 'weeklybets', '#weeklybets'])
async def get_weekly(message: types.Message):
    p_btc, _, _ = get_price("btc")
    p_eth, _, _ = get_price("eth")
    amount=r.get("BTC_*") or 'Not Sure'
    out = "BTC Bets (Current=" + str(round(p_btc,0)) + "):\n"
    for key in r.scan_iter("BTC_*"):
        a = r.get(key).decode('utf-8') or "NONE"
        d = get_abs_difference(a, p_btc)
        out = out + str(key.decode('utf-8')).replace("BTC_","") + " => " + a + "  -- DIFF = " + str(round(d,1)) + "\n"
    out = out + "\nETH Bets (Current=" + str(round(p_eth,0)) + "):\n"
    for key in r.scan_iter("ETH_*"):
        a = r.get(key).decode('utf-8') or "NONE"
        d = get_abs_difference(a, p_eth)
        out = out + str(key.decode('utf-8')).replace("ETH_","") + " => " + a + "  -- DIFF = " + str(round(d,1)) + "\n"
    await bot.send_message(chat_id=message.chat.id, text=out)

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['bet btc ([0-9.,a-zA-Z]*) eth ([0-9.,a-zA-Z]*)']))
async def set_weekly(message: types.Message, regexp_command):
    try:
        amount = regexp_command.group(1)
        amount_eth = regexp_command.group(2)
        r.set("BTC_" + message.from_user.mention, amount)
        r.set("ETH_" + message.from_user.mention, amount_eth)
        await message.reply(f'Gotit. Bet for first Mars seat: BTC {amount}, ETH {amount_eth}')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /bet btc 12.3k eth 1.2k')


async def on_startup(dp):
    logging.warning(
        'Starting connection. ')
    await bot.set_webhook(WEBHOOK_URL,drop_pending_updates=True)


async def on_shutdown(dp):
    logging.warning('Bye! Shutting down webhook connection')


def main():
    logging.basicConfig(level=logging.INFO)
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        skip_updates=True,
        on_startup=on_startup,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )