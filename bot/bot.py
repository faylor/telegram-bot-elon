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

from .twits import Twits, get_stream
from .thecats import getTheApiUrl
from .prices import get_price, weekly_tally, get_abs_difference, round_sense

r = redis.from_url(REDIS_URL)

bot = Bot(token=TELEGRAM_BOT)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())
twits = Twits()


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

@dp.message_handler(commands=['elon', 'Elon', 'elon?', 'Elon?', 'help', 'me'])
async def send_help(message: types.Message):
    await message.reply(f'SUP! {message.from_user.first_name}? \n Get Price: /$btc /$aave ..etc \n\n Watch Table: /$ /lambo /prices \n Add Coin To Watch: /watch <coin> eg: /watch eth \n Mark A Point: /buy btc \n Remove a Point: /sell btc \n View Balance: /hodl \n\n bets: \n Start a new week: /startbets \n Finish a week: /stopbets \n Add your bet: /bet btc 12.3k eth 1.2k \n View current bets: /bets \n View Winners: /totes or /leaderboard \n\n Fun:\n /jelly <name>  \n /green<anything> \n /red<anything> \n /doge \n /cat \n /remind \n\n * NOTHING I SAY IS FINANCIAL ADVICE * NOTHING! Built For Fun.')

@dp.message_handler(commands=['remind'])
async def send_reminder(message: types.Message):
    await message.reply(f'Yo! Get a wallet. Idjiot.')

@dp.message_handler(commands=['add1'])
async def add_user(message: types.Message):
    logging.warn('user:' + message.from_user.mention)
    await message.reply('user:' + message.from_user.mention)
    config = r.get(message.chat.id)
    if config is None:
        config = {}
    else:
        config = json.loads(config)
    if "winners_list" not in config:
        config["winners_list"] = []
    if message.from_user.mention not in config["winners_list"]:
        config["winners_list"][message.from_user.mention] = 1
    else:
        config["winners_list"][message.from_user.mention] = int(config["winners_list"][message.from_user.mention]) + 1
    logging.info(json.dumps(config))
    r.set(message.chat.id, json.dumps(config))

@dp.message_handler(commands=['minus1'])
async def minus_user(message: types.Message):
    logging.warn('user:' + message.from_user.mention)
    await message.reply('user:' + message.from_user.mention)
    config = r.get(message.chat.id)
    if config is not None:
        config = json.loads(config)
        if "winners_list" in config and message.from_user.mention in config["winners_list"]:
            config["winners_list"][message.from_user.mention] = int(config["winners_list"][message.from_user.mention]) - 1
            logging.info(json.dumps(config))
            r.set(message.chat.id, json.dumps(config))

def get_user_price_config(user):
    try:
        config = r.get("prices_" + user)
        if config is None:
            return "usd"
        else:
            return config.decode('UTF-8')
    except Exception as e:
        return "usd"

@dp.message_handler(commands=['prices', 'watching', 'btc', 'lambo', 'whenlambo', 'lambos', 'whenlambos', 'price', '$', '£', '€'])
async def prices(message: types.Message):
    chat_id = message.chat.id
    mains = ["BTC", "ETH", "GRT", "LTC", "ADA", "AAVE", "DOGE", "ZIL"]
    try:
        config = json.loads(r.get(message.chat.id))
        logging.info(json.dumps(config))
        if "watch_list" in config:
            mains = config["watch_list"]
    except Exception as ex:
        logging.info("no config found, ignore")
    in_prices = get_user_price_config(message.from_user.mention).upper()
    out = f"<pre>Symbol|     {in_prices}          | +/- 1hr / 24hr\n"
    totes = 0
    for l in mains:
        p, c, c24, btc_price = get_price(l)
        totes = totes + c
        l = l.ljust(5, ' ')
        label_on_change = "   "
        if c > 3:
            label_on_change = "++++"
        elif c > 2:
            label_on_change = "  ++"
        elif c > 0:
            label_on_change = "   +"
        if in_prices == "USD":
            prices = str(round_sense(p))
        else:
            prices = str(round(btc_price,8))
        prices = prices.ljust(12, ' ')
        change = label_on_change + str(round(c,1))
        change24 = str(round(c24,1))
        out = out + f"{l} | {prices} | {change} / {change24}\n"
    if totes < 0:
        out = out + "</pre>OUCH, NO LAMBO FOR YOU!" 
    elif totes > 6:
        out = out + "</pre>OK OK, LAMBO FOR YOU!"
    else:
        out = out + "</pre>MEH, MAYBE LAMBO. HODL."
    await bot.send_message(chat_id=chat_id, text=out, parse_mode="HTML")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['\$([a-zA-Z]*)']))
async def send_price_of(message: types.Message, regexp_command):
    try:
        symbol = regexp_command.group(1)
        p, c, c24, btc_price = get_price(symbol)
        await bot.send_message(chat_id=message.chat.id, text=f"<pre>{symbol}: ${round_sense(p)}  {round(btc_price,8)}BTC  \nChange: {round(c,2)}% 1hr    {round(c24,2)}% 24hr</pre>", parse_mode="HTML")
        saved = r.get("At_" + symbol.lower() + "_" + message.from_user.mention)
        if saved is not None:
            saved = float(saved.decode('utf-8'))
            changes = round(100 * (p - saved) / saved, 2)
            await bot.send_message(chat_id=message.chat.id, text=f"<pre>You marked at {saved}, changed by {changes}%</pre>", parse_mode="HTML")
    except Exception as e:
        logging.warn("Could convert saved point:" + str(e))

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['hodl([\sa-zA-Z]*)']))
async def send_balance(message: types.Message, regexp_command):
    try:
        bysymbol = regexp_command.group(1)
        saves = r.scan_iter("At_*_" + message.from_user.mention)
        out = "HODLing:\n"
        out = out + "<pre>| Coin |  Buy Price |  Price     |  +/-  |\n"
        total_change = float(0.00)
        for key in saves:
            symbol = key.decode('utf-8').replace("At_", "").replace("_" + message.from_user.mention,"")
            p, c, c24, btc_price = get_price(symbol)
            if float(p) > 0:
                value = r.get(key)
                if value is not None:
                    value = value.decode('utf-8')
                    if "{" in value:
                        js = json.loads(value)
                        usd_price = float(js["usd"])
                        buy_btc_price = float(js["btc"])
                    else:
                        usd_price = float(value)
                        buy_btc_price = "UNKNOWN"
                    
                    if bysymbol is not None and "btc" in bysymbol.lower():
                        price = str(round(btc_price,8)).ljust(10,' ')
                        if buy_btc_price == "UNKNOWN":
                            buy_price = buy_btc_price.ljust(10,' ')
                            change = 0
                        else:
                            buy_price = str(round_sense(buy_btc_price)).ljust(10,' ')
                            change = round(100 * (btc_price - buy_btc_price) / buy_btc_price, 2)
                    else:
                        buy_price = str(round_sense(usd_price)).ljust(10,' ')
                        price = str(round_sense(p)).ljust(10,' ')
                        change = round(100 * (p - usd_price) / usd_price, 2)
                    total_change = total_change + change
                    change = str(round(change,1)).ljust(5,' ')
                    symbol = symbol.ljust(4, ' ')
                    out = out + f"| {symbol} | {buy_price} | {price} | {change} | \n"
            else:
                out = out + f"| {symbol} | NA | NA | NA | \n"
        total_change = round(total_change, 2)
        out = out + "</pre>\nTOTAL CHANGE = " + str(total_change) + "%"
        await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")
    except Exception as e:
        logging.warn("Couldnt get hodl data:" + str(e))

@dp.message_handler(commands=['startbets', 'startweekly', 'startweeklybets', 'start#weeklybets'])
async def start_weekly(message: types.Message):
    for key in r.scan_iter("BTC_*"):
        r.delete(key)
    for key in r.scan_iter("ETH_*"):
        r.delete(key)
    await bot.send_message(chat_id=message.chat.id, text="DELETED BETS. Good Luck.")

@dp.message_handler(commands=['bets', 'weekly', 'weeklybets', '#weeklybets'])
async def get_weekly(message: types.Message):
    out, _, _ = weekly_tally(message)
    await bot.send_message(chat_id=message.chat.id, text=out)

@dp.message_handler(commands=['clearbetstotals'])
async def clear_weekly_totals(message: types.Message):
    config = r.get(message.chat.id)
    if config is not None:
        config = json.loads(config)
        if "winners_list" in config:
            config["winners_list"] = {}
            r.set(message.chat.id, json.dumps(config))
            await bot.send_message(chat_id=message.chat.id, text='Cleared Table.')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['userprices ([a-zA-Z]*)']))
async def set_user_prices(message: types.Message, regexp_command):
    try:
        type = regexp_command.group(1)
        if type is None or type.lower() != "btc":
            await message.reply(f'{message.from_user.first_name} Fail. You Idiot. /userprices btc   or /userprices usd')
            return
        if type.lower() == "btc" or type.lower() == "usd":
            user = message.from_user.mention
            r.set("prices_" + user, type.lower())
            await message.reply(f'Gotit. Prices in {type} for {user}')
        else:
            await message.reply(f'{message.from_user.first_name} Fail. You Idiot. We only accept btc or usd prices. /userprices btc   or /userprices usd')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /bet btc 12.3k eth 1.2k')

@dp.message_handler(commands=['stopbets', 'stopweekly', 'stopweeklybets', 'stop#weeklybets'])
async def finish_weekly(message: types.Message):
    out, winning_btc, winning_eth = weekly_tally(message)
    await bot.send_message(chat_id=message.chat.id, text=out)
    await bot.send_message(chat_id=message.chat.id, text=f'BTC winner = {winning_btc}, ETH winner = {winning_eth}')
    config = r.get(message.chat.id)
    if config is None:
        config = {}
    else:
        config = json.loads(config)
    if "winners_list" not in config:
        config["winners_list"] = {}
    if winning_btc not in config["winners_list"]:
        config["winners_list"][winning_btc] = 1
    else:
        config["winners_list"][winning_btc] = int(config["winners_list"][winning_btc]) + 1
    if winning_eth not in config["winners_list"]:
        config["winners_list"][winning_eth] = 1
    else:
        config["winners_list"][winning_eth] = int(config["winners_list"][winning_eth]) + 1
    logging.info(json.dumps(config))
    r.set(message.chat.id, json.dumps(config))
    await bot.send_message(chat_id=message.chat.id, text=f'Added To Table: ' + json.dumps(config["winners_list"]))
    await bot.send_message(chat_id=message.chat.id, text='To clear all bets for this week, run /startbets')

@dp.message_handler(commands=['leader', 'leaderboard', 'winning', 'totes'])
async def total_weekly(message: types.Message):
    config = r.get(message.chat.id)
    if config is None:
        config = {"winners_list":[]}
    else:
        config = json.loads(config)
    
    if "winners_list" in config:
        out = "TOTES WINNERS: \n"
        logging.error(config["winners_list"])
        for k, v in config["winners_list"].items():
            out = out + str(k) + " == " + str(v) + "\n"
        await bot.send_message(chat_id=message.chat.id, text=out)
    else:
        await bot.send_message(chat_id=message.chat.id, text="No Winners Yet, bet first then stopbets... clown.")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['bet btc ([0-9.,a-zA-Z]*) eth ([0-9.,a-zA-Z]*)']))
async def set_weekly(message: types.Message, regexp_command):
    try:
        amount = regexp_command.group(1)
        amount_eth = regexp_command.group(2)
        cid = str(message.chat.id)
        r.set(f"{cid}_BTC_" + message.from_user.mention, amount)
        r.set(f"{cid}_ETH_" + message.from_user.mention, amount_eth)
        await message.reply(f'Gotit. Bet for first Mars seat: BTC {amount}, ETH {amount_eth}')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /bet btc 12.3k eth 1.2k')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['buy ([0-9.,a-zA-Z]*)']))
async def set_buy_point(message: types.Message, regexp_command):
    try:
        symbol = regexp_command.group(1)
        p, _, _, btc_price = get_price(symbol)
        js = {"usd":p,"btc":btc_price}
        r.set("At_" + symbol.lower() + "_" + message.from_user.mention, json.dump(js))
        await message.reply(f'Gotit. {symbol} at ${round_sense(p)} or {round(btc_price,8)} BTC marked')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /buy btc')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['sell ([0-9.,a-zA-Z]*)']))
async def set_sell_point(message: types.Message, regexp_command):
    try:
        symbol = regexp_command.group(1)
        p, _, _, btc_price = get_price(symbol)
        js = r.get("At_" + symbol.lower() + "_" + message.from_user.mention).decode('utf-8')
        if js is not None:
            if "{" in js:
                js = json.loads(js)
                saved = js["usd"]
                saved_btc = js["btc"]
                if saved_btc > 0:
                    changes_btc = round(100 * (btc_price - float(saved_btc)) / float(saved_btc), 2)
                else:
                    changes_btc = "NA"
            else:
                saved = float(js)
                saved_btc = 1
                changes_btc = "<UNKNOWN>"
            if saved > 0:
                changes = round(100 * (p - float(saved)) / float(saved), 2)
            else:
                changes = "NA"
            await message.reply(f'Sold. {symbol} final diff in USD {changes}%  or in BTC {changes_btc}')
        r.delete("At_" + symbol.lower() + "_" + message.from_user.mention)
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /sell btc')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['watch ([a-zA-Z]*)']))
async def add_to_prices(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1)
        logging.info("config")
        config = r.get(message.chat.id)
        if config is None:
            config = {}
        else:
            config = json.loads(config)
        logging.info(json.dumps(config))
        a, _, _, _ = get_price(new_coin)
        if "watch_list" not in config:
            config["watch_list"] = []
        if a == 0:
            await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Code Not Found. Try /watch $aave')
        else:
            if new_coin in config["watch_list"]:
                await message.reply(f'{message.from_user.first_name} Fail. Already Watching This One. ' + str(config["watch_list"]))
            else:
                config["watch_list"].append(new_coin)
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'Gotit. Added ' + new_coin)
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')


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
