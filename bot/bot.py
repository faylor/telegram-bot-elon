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


def getUrl():
    #obtain a json object with image details
    #extract image url from the json object
    contents = requests.get('https://api.thecatapi.com/v1/images/search')
    js = contents.json()
    print(js)
    url = js[0]["url"]
    return url

@dp.message_handler(text=['doge', 'cat'])
async def sendImage(message: types.Message):
    url = getUrl()
    await bot.send_photo(chat_id=message.chat.id, photo=url)

@dp.message_handler(text=['Jelly', 'jelly', 'jelly hands', '#jellyhands'])
async def sendTable(message: types.Message):
    name = message.from_user.first_name
    await message.reply(f'Hello {name}, you have Jelly Hands.')

@dp.message_handler(text=['elon?', 'Elon?'])
async def sendTable(message: types.Message):
    await message.reply(f'Hello {message.from_user.first_name}, I am a busy man, what? \n Get Price: /$btc /$aave ..etc \n Show Table: /lambo /prices')

@dp.message_handler(commands=['elon', 'Elon', 'elon?', 'Elon?', 'help'])
async def send_help(message: types.Message):
    await message.reply(f'SUP! {message.from_user.first_name}? \n Get Price: /$btc /$aave ..etc \n Show Table: /lambo /prices')


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

@dp.message_handler(commands=['bets', 'weekly', 'weeklybets', '#weeklybets'])
async def get_weekly(message: types.Message):
    amount=r.get(message.from_user.username) or 'Not Sure'
    await message.reply(f'{message.from_user.first_name} BTC {amount}')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['bet btc ([0-9.,a-zA-Z]*)']))
async def set_weekly(message: types.Message, regexp_command):
    amount = regexp_command.group(1)
    print(amount)
    r.set(message.from_user.mention, amount)
    await message.reply(f'{message.from_user.first_name} BTC {amount}')


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