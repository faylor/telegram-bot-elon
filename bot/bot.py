import logging
import json
import requests
import redis
import asyncio
from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher, filters
from aiogram.utils.executor import start_webhook
from aiogram.dispatcher.webhook import SendMessage
from aiogram.utils.markdown import escape_md
from bot.settings import (TELEGRAM_BOT, HEROKU_APP_NAME,
                          WEBHOOK_URL, WEBHOOK_PATH,
                          WEBAPP_HOST, WEBAPP_PORT, REDIS_URL)

from aiogram.contrib.fsm_storage.memory import MemoryStorage

from .twits import Twits, get_stream
from .thecats import getTheApiUrl, get_a_fox, search_pix
from .prices import get_price, round_sense, get_news, get_rapids

r = redis.from_url(REDIS_URL)

bot = Bot(token=TELEGRAM_BOT)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())
twits = Twits()

from .watchalts import *
from .watchlist import *
from .wallet import *
from .virtualwallet import *
from .bets import *
from .user import *
from .chart import *


@dp.message_handler(commands=['elon', 'Elon', 'elon?', 'Elon?', 'help', 'me', 'start'])
async def send_help(message: types.Message):
    out = """  
Elons A Bot: 

SETTINGS:
  User Prices in BTC: /userprices btc   
  User Prices in USD (Default): /userprices usd

COIN INFORMATION:
  Get Price: /$btc /$aave ..etc
  News Summary: /news btc 

WATCH COINS (PER CHAT):
  Watch table: /$ /lambo /prices 
  Add To watch: /watch <coin> (eg: /watch eth)
  Remove from watch: /remove <coin> (eg: /remove aave)

  Watch ATH on Alts: /alts
  Add To Alts: /watchalt <coin> (eg: /watchalt zil)
  Remove from watchalt: /removealt <coin> (eg: /removealt aave)

BAGS WALLET (Advanced - Per Chat):
  Buy: /grab btc
  Sell: /dump btc
  View Balance (in user price setting): /bag     
  View Balance in BTC: /bag btc     
  View Balance in USD: /bag usd
  
  LEAGUE (Advanced):
    Clear Bags: /clearbags
    Give Everone 1000: /gimme
    View Ladder: /ladder   
    ** Score based on USD. 

HODL WALLET (Basic - Warning Per User!):
  Buy: /buy btc     or multple: /buy eth btc ada
  BuyAt: /buyat eth 34521.23 0.21   (Price in USD and BTC)
  Sell: /sell btc    or mulitple: /sell eth btc aave
  Remove:/deletecoin doge aave etc.  Deletes without counting score
  View Balance (in user price setting): /hodl     
  View Balance in BTC: /hodl btc     
  View Balance in USD: /hodl usd

  LEAGUE (Basic):
    Start Season: /newseason
    Show Standings: /league      
    ** Score is simply adding up change % on each sell action. 

SUMMARY:
  Prices, Alts and Virtual Wallet: /summary

GUESS THE PRICE GAME:
  Start a new round: /startbets  
  Add your bet: /bet btc 12.3k eth 1.2k 
  View current bets: /bets
  Finish a round: /stopbets
  View Winners: /totes or /leaderboard
  Clear Winner: /clearbetstotals
  Update Winners, adds one to the user calling it: /add1
  Update Winners, removes one from calling user: /minus1

Fun: 
  /jelly <name>  
  /green <anything> 
  /red <anything> 
  /doge 
  /cat
  /fox  or /foxy
  /pix <anything>
  /remind

* NOTHING I SAY IS FINANCIAL ADVICE * NOTHING! Built For Fun.
    """
    await bot.send_message(chat_id=message.chat.id, text=out)


@dp.message_handler(commands=['startstream'])
async def startStream(message: types.Message):
    try:
        logging.warn("____CHAT IT_____ " + str(message.chat.id))
        twits.add_chat_id(message.chat.id)
        await bot.send_message(chat_id=message.chat.id, text="Trying to running...")
        get_stream(twits)
        await bot.send_message(chat_id=message.chat.id, text="Running...")
    except Exception as e:
        logging.error("START UP ERROR:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Start Stream")


@dp.message_handler(commands=['stopstream'])
async def stopStream(message: types.Message):
    try:
        twits.remove_chat_id(message.chat.id)
    except Exception as e:
        logging.error(str(e))
        await bot.send_message(chat_id=message.chat.id, text="Failed to Stop Stream")


@dp.message_handler(commands=['doge', 'dog'])
async def sendDogImage(message: types.Message):
    url = getTheApiUrl('dog')
    await bot.send_photo(chat_id=message.chat.id, photo=url)

@dp.message_handler(commands=['cate', 'cat'])
async def sendCatImage(message: types.Message):
    url = getTheApiUrl('cat')
    await bot.send_photo(chat_id=message.chat.id, photo=url)

@dp.message_handler(commands=['fox', 'foxy'])
async def sendFoxImage(message: types.Message):
    url = get_a_fox()
    await bot.send_photo(chat_id=message.chat.id, photo=url)

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['pix ([\s0-9.,a-zA-Z]*)']))
async def get_pix(message: types.Message, regexp_command):
    name = regexp_command.group(1)
    url = search_pix(name)
    if url is None:
        await bot.send_message(chat_id=message.chat.id, text=f'Sorry Nothing Found.')
    else:
        await bot.send_photo(chat_id=message.chat.id, photo=url)

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['red([a-zA-Z]*)']))
async def send_red(message: types.Message, regexp_command):
    await bot.send_sticker(chat_id=message.chat.id, sticker="https://tenor.com/view/spacex-fail-landing-explosion-explode-gif-19509668")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['jelly([\sa-zA-Z]*)']))
async def send_jelly(message: types.Message, regexp_command):
    name = regexp_command.group(1)
    await bot.send_message(chat_id=message.chat.id, text=f'Hello {name}, you have Jelly Hands. Love Elon. Kisses.')
    await bot.send_sticker(chat_id=message.chat.id, sticker="https://tenor.com/view/laughing-spacex-elon-musk-elon-musk-gif-13597458")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['green([a-zA-Z]*)']))
async def send_green(message: types.Message, regexp_command):
    await bot.send_sticker(chat_id=message.chat.id, sticker="https://tenor.com/view/spacex-bitcoin-rd_btc-elon-musk-elon-gif-20158067")

@dp.message_handler(commands=['remind'])
async def send_reminder(message: types.Message):
    await message.reply(f'Yo! Get a wallet. Idjiot.')


# @dp.message_handler(commands=['summary'])
# async def send_summary(message: types.Message):
#     await prices(message)
#     await prices_alts(message)
#     await send_balance(message, None)


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['\$([a-zA-Z]*)']))
async def send_price_of(message: types.Message, regexp_command):
    try:
        symbol = regexp_command.group(1)
        p, c, c24, btc_price = get_price(symbol)
        await bot.send_message(chat_id=message.chat.id, text=f"<pre>{symbol}: ${round_sense(p)}  {round(btc_price,8)}BTC  \nChange: {round(c,2)}% 1hr    {round(c24,2)}% 24hr</pre>", parse_mode="HTML")
        saved = r.get("At_" + symbol.lower() + "_" + message.from_user.mention)
        if saved is not None:
            saved = saved.decode('utf-8')
            if "{" in saved:
                js = json.loads(saved)
                saved = float(js["usd"])
                saved_btc = float(js["btc"])
            else:
                saved = float(saved)
                saved_btc = 0
            changes = round(100 * (p - saved) / saved, 2)
            await bot.send_message(chat_id=message.chat.id, text=f"<pre>You marked at ${saved} and {saved_btc}BTC, changed by {changes}%</pre>", parse_mode="HTML")
        await candle(message, regexp_command)
    except Exception as e:
        logging.warn("Could convert saved point:" + str(e))

@dp.message_handler(commands=['pump', 'rapid'])
async def send_rapids(message: types.Message):
    try:
        array_rapids = get_rapids()
        out = ""
        i = 0
        for rap in array_rapids:
            if i < 15:
                out = out + rap["pair"] + ": " + str(rap["side"]) + " " + str(rap["change_detected"]) + "% @" + str(rap["timestamp"]) + "\n"
                i = i + 1
            else:
                break
        await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")
                
    except Exception as e:
        logging.warn("Could not load rapids:" + str(e))

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['news ([a-zA-Z]*)']))
async def find_news(message: types.Message, regexp_command):
    try:
        symbol = regexp_command.group(1)
        title, content = get_news(symbol)
        await bot.send_message(chat_id=message.chat.id, text=f"{title}\n\n{content}", parse_mode="HTML")
    except Exception as e:
        logging.warn("Could not get news:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="<pre>Failed to get news for this coin</pre>", parse_mode="HTML")


async def on_startup(dp):
    logging.warning('Starting connection.')
    await bot.set_webhook(WEBHOOK_URL,drop_pending_updates=True)
    twits.prepare_stream()
    twits.start_stream()
    get_stream(twits)

async def on_shutdown(dp):
    twits.close()
    logging.warning('Bye! Shutting down webhook connection')


def main():
    logging.basicConfig(level=logging.INFO)
    try:
        start_webhook(
            dispatcher=dp,
            webhook_path=WEBHOOK_PATH,
            skip_updates=True,
            on_startup=on_startup,
            host=WEBAPP_HOST,
            port=WEBAPP_PORT,
        )
    except Exception as e:
        logging.error("Error:" + str(e))
