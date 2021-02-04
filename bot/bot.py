import logging
import requests
import json
from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher, filters
from aiogram.utils.executor import start_webhook
from bot.settings import (TELEGRAM_BOT, HEROKU_APP_NAME,
                          WEBHOOK_URL, WEBHOOK_PATH,
                          WEBAPP_HOST, WEBAPP_PORT)

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

@dp.message_handler(text=['me', 'you'])
async def sendTable(message: types.Message):
    name = message.from_user.first_name
    if "josh" in name.lower():
        await message.reply(f'Hello {name}, you are Jelly Hands')
    else:
        await message.reply(f'Hello {name}, you are HODLing strong')

@dp.message_handler(text=['elon?', 'Elon?'])
async def sendTable(message: types.Message):
    await message.reply(f'Hello {message.from_user.first_name}, I am a busy man, what?')


@dp.message_handler(commands=['prices', 'btc', 'lambo', 'whenlambo', 'price', '$'])
async def prices(message: types.Message):
    chat_id = message.chat.id
    mains = ["BTC", "ETH", "GRT", "LTC", "ADA", "AAVE", "DOGE"]
    out = "| Symbol | Price | Change (1hr) |\n|--------|-------|--------|\n"
    totes = 0
    for l in mains:
        p, c = get_price(l)
        totes = totes + c
        out = out + f"|{l}    | ${round(p,4)}    | {round(c,1)}   | \n"
    if totes < 0:
        out = out + "OUCH, NO LAMBO FOR YOU!\n" 
    elif totes > 15:
        out = out + "OK OK, LAMBO FOR YOU!\n"
    else:
        out = out + "MEH, MAYBE LAMBO. HODL.\n"
    await bot.send_message(chat_id=chat_id, text=out, parse_mode="Markdown")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['$([a-zA-Z]*)']))
async def send_welcome(message: types.Message, regexp_command):
    await message.reply(f"You have requested a price for <code>{regexp_command.group(1)}</code>")

@dp.message_handler(text=['$doge'])
async def prices(message: types.Message):
    p, c = get_price("doge")
    await bot.send_message(chat_id=message.chat.id, text=f"{l} ${round(p,4)} {round(c,1)}% 1 hour")
    
def get_price(label):
    price, change_1hr = 0, 0
    logging.error("DOWNLOADING " + label)    
    try:
        url = "https://data.messari.io/api/v1/assets/" + label + "/metrics"
        resp = requests.get(url)
        js = resp.json()
        price = js["data"]["market_data"]["price_usd"]
        change_1hr = js["data"]["market_data"]["percent_change_usd_last_1_hour"]
    except Exception as e:
        logging.error(e)
    return price, change_1hr


# @dp.message_handler()
# async def echo(message: types.Message):
#     logging.warning(f'Recieved a message from {message.from_user}')
#     await bot.send_message(message.chat.id, message.text)


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