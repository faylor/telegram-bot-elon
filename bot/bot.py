import logging

from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
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
def sendImage(update, context):
    url = getUrl()
    chat_id = update.message.chat_id
    context.bot.send_photo(chat_id=chat_id, photo=url)

@dp.message_handler(text=['me', 'you'])
def sendTable(update, context):
    name = update.effective_user.first_name
    if "josh" in name.lower():
        update.message.reply_text(f'Hello {update.effective_user.first_name}, you are Jelly Hands')
    else:
        update.message.reply_text(f'Hello {update.effective_user.first_name}, you are HODLing strong')

@dp.message_handler(text=['prices', 'btc', 'lambo', 'whenlambo', 'price', '$'])
def prices(update, context):
    chat_id = update.message.chat_id
    mains = ["BTC", "ETH", "GRT", "LTC", "ADA", "AAVE", "DOGE"]
    out = ""
    totes = 0
    for l in mains:
        p, c = get_price(l)
        totes = totes + c
        context.bot.send_message(chat_id=chat_id, text=f"{l} ${round(p,4)} {round(c,1)}% 1 hour")
    
    if totes<0:
        context.bot.send_message(chat_id=chat_id, text="OUCH, NO LAMBO FOR YOU!")
    elif totes>15:
        context.bot.send_message(chat_id=chat_id, text="OK OK, LAMBO FOR YOU!")
    else:
        context.bot.send_message(chat_id=chat_id, text="MEH, MAYBE LAMBO. HODL.")

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