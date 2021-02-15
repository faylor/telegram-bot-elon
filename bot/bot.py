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
from .prices import get_price, weekly_tally, get_abs_difference, round_sense, get_news, get_alt_watch

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

VIRTUAL WALLET:
  Buy: /buy btc     or multple: /buy eth btc ada
  Sell: /sell btc    or mulitple: /sell eth btc aave
  View Balance (in user price setting): /hodl     
  View Balance in BTC: /hodl btc     
  View Balance in USD: /hodl usd
  Clear Score**: /clearscore      
  ** Score is simply adding up change % on each sell action. 

GUESS THE PRICE GAME:
  Start a new round: /startbets  
  Add your bet: /bet btc 12.3k eth 1.2k 
  View current bets: /bets
  Finish a round: /stopbets
  View Winners: /totes or /leaderboard
  Clear Winner: /clearbetstotals
  Update Winners, dds one to the user calling it: /add1
  Update Winners, removes one from calling user: /minus1

Fun: 
  /jelly <name>  
  /green <anything> 
  /red <anything> 
  /doge 
  /cat 
  /remind

* NOTHING I SAY IS FINANCIAL ADVICE * NOTHING! Built For Fun.
    """
    await bot.send_message(chat_id=message.chat.id, text=out)

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

def get_change_label(c):
    label_on_change = "🔻"
    if c > 3:
        label_on_change = "🚀"
    elif c > 0:
        label_on_change = "↗️"
    elif c == 0:
        label_on_change = "  "
    elif c > -3:
        label_on_change = "↘️"
    return label_on_change + str(round(c,1)).replace("-","")


@dp.message_handler(commands=['alts'])
async def prices_alts(message: types.Message):
    chat_id = message.chat.id
    mains = ["ETH", "GRT", "LTC", "ADA", "NANO", "NEO", "AAVE", "DOGE", "ZIL"]
    try:
        config = json.loads(r.get(message.chat.id))
        logging.info(json.dumps(config))
        if "watch_list_alts" in config:
            mains = config["watch_list_alts"]
    except Exception as ex:
        logging.info("no config found, ignore")
    in_prices = get_user_price_config(message.from_user.mention).upper()
    out = [f"<pre>{in_prices} 1hr  24hr | ATH days from | ATH % down"]
    
    for l in mains:
        c, c24, c_btc, c_btc_24, days_since, ath_down = get_alt_watch(l)
        l = l.ljust(5, ' ')
        
        if in_prices == "USD":
            change = get_change_label(c)
            change24 = get_change_label(c24)
        else:
            change = get_change_label(c_btc)
            change24 = get_change_label(c_btc_24)
        s = f"{l} {change}   {change24} | {days_since} | {round(ath_down,1)}%"
        if len(out) > 2:
            i = 1
            while i < len(out) and change < out[i]:
                i = i + 1
            out.insert(i, s)
        else:
            out.append(s)

    await bot.send_message(chat_id=chat_id, text="\n".join(out) + "</pre>", parse_mode="HTML")

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
    out = f"<pre>       {in_prices}    | 1hr      24hr\n"
    totes = 0
    for l in mains:
        p, c, c24, btc_price = get_price(l)
        totes = totes + c
        l = l.ljust(5, ' ')
        
        if in_prices == "USD":
            prices = str(round_sense(p))
        else:
            prices = str(round(btc_price,8))
        prices = prices.ljust(7, ' ')
        change = get_change_label(c)
        change24 = get_change_label(c24)
        out = out + f"{l} {prices} |{change}    {change24}\n"
    if totes < 0:
        out = out + "</pre>\n\n ☠️☠️☠️☠️☠️☠️" 
    elif totes > 6:
        out = out + "</pre>\n\n 🏎🏎🏎🏎🏎"
    else:
        out = out + "</pre>\n\n 🤷🏽🤷🏽🤷🏽🤷🏽🤷🏽"
    await bot.send_message(chat_id=chat_id, text=out, parse_mode="HTML")

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
    except Exception as e:
        logging.warn("Could convert saved point:" + str(e))

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['news ([a-zA-Z]*)']))
async def find_news(message: types.Message, regexp_command):
    try:
        symbol = regexp_command.group(1)
        title, content = get_news(symbol)
        await bot.send_message(chat_id=message.chat.id, text=f"{title}\n\n{content}", parse_mode="HTML")
    except Exception as e:
        logging.warn("Could not get news:" + str(e))
        await bot.send_message(chat_id=message.chat.id, text="<pre>Failed to get news for this coin</pre>", parse_mode="HTML")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['hodl([\sa-zA-Z]*)']))
async def send_balance(message: types.Message, regexp_command):
    try:
        bysymbol = regexp_command.group(1)
        saves = r.scan_iter("At_*_" + message.from_user.mention)
        out = "HODLing:\n"
        in_prices = get_user_price_config(message.from_user.mention)
        out = out + "<pre>       Buy At   |  Price   |  +/-  \n"
        total_change = float(0.00)
        counter = 0
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
                    
                    if symbol.lower() != "btc" and ((bysymbol is not None and "btc" in bysymbol.lower()) or in_prices == "btc"):
                        price = str(round(btc_price,8)).ljust(10,' ')
                        if buy_btc_price == "UNKNOWN" or buy_btc_price == 0:
                            buy_price = buy_btc_price.ljust(8,' ')
                            change = 0
                        else:
                            buy_price = str(round(buy_btc_price, 6)).ljust(8,' ')
                            change = round(100 * (btc_price - buy_btc_price) / buy_btc_price, 2)
                    else:
                        buy_price = str(round_sense(usd_price)).ljust(8,' ')
                        price = str(round_sense(p)).ljust(8,' ')
                        if usd_price == 0:
                            change = 0
                        else:
                            change = round(100 * (p - usd_price) / usd_price, 2)
                    total_change = total_change + change
                    counter = counter + 1
                    change = get_change_label(change).ljust(5,' ')
                    symbol = symbol.ljust(4, ' ')
                    out = out + f"{symbol} | {buy_price} | {price} | {change}\n"
            else:
                out = out + f"| {symbol} | NA | NA | NA | \n"
        total_change = round(total_change, 2)
        out = out + "</pre>\nSUMMED CHANGE = " + str(total_change) + "%"
        if counter > 0:
            out = out + "\nAVERAGE CHANGE = " + str(round(total_change/counter,2)) + "%"
        current_score = r.get("score_" + message.from_user.mention)
        if current_score is None:
            current_score = 0
        else:
            current_score = float(current_score.decode('utf-8'))
        out = out + "\nTOTAL SCORE = " + str(round(current_score,2)) + "\n"
        await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")
    except Exception as e:
        logging.warn("Couldnt get hodl data:" + str(e))

@dp.message_handler(commands=['startbets', 'startweekly', 'startweeklybets', 'start#weeklybets'])
async def start_weekly(message: types.Message):
    cid = str(message.chat.id)
    for key in r.scan_iter(f"{cid}_BTC_*"):
        r.delete(key)
    for key in r.scan_iter(f"{cid}_ETH_*"):
        r.delete(key)
    await bot.send_message(chat_id=message.chat.id, text="DELETED BETS. Good Luck.")

@dp.message_handler(commands=['bets', 'weekly', 'weeklybets', '#weeklybets'])
async def get_weekly(message: types.Message):
    out, _, _ = weekly_tally(message, r)
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
        if type is None:
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

@dp.message_handler(commands=['clearscore'])
async def clear_user_balance(message: types.Message):
    try:
        user = message.from_user.mention
        r.set("score_" + user, 0)
        await message.reply(f'Reset Score for {user}')
    except Exception as e:
        await message.reply(f'{message.from_user.first_name} Failed to reset score. Contact... meh')


def add_win_for_user(config, mention):
    mention = mention.strip()
    if mention not in config["winners_list"]:
        config["winners_list"][mention] = 1
    else:
        config["winners_list"][mention] = int(config["winners_list"][mention]) + 1
    
@dp.message_handler(commands=['stopbets', 'stopweekly', 'stopweeklybets', 'stop#weeklybets'])
async def finish_weekly(message: types.Message):
    out, winning_btc, winning_eth = weekly_tally(message, r)
    await bot.send_message(chat_id=message.chat.id, text=out)
    await bot.send_message(chat_id=message.chat.id, text=f'BTC winner = {winning_btc}, ETH winner = {winning_eth}')
    config = r.get(message.chat.id)
    if config is None:
        config = {}
    else:
        config = json.loads(config)
    if "winners_list" not in config:
        config["winners_list"] = {}
    if "," in winning_btc:
        winners = winning_btc.split(",")
        for winner in winners:
            add_win_for_user(config, winner)
    else:
        add_win_for_user(config, winning_btc)
    if "," in winning_eth:
        winners = winning_eth.split(",")
        for winner in winners:
            add_win_for_user(config, winner)
    else:
        add_win_for_user(config, winning_eth)
    
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


def get_symbol_list(symbols):
    if "," in symbols:
        symbol_split = symbols.split(",")
    elif " " in symbols:
        symbol_split = symbols.split()
    else:
        symbol_split = [symbols]
    return symbol_split

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['buy ([\s0-9.,a-zA-Z]*)']))
async def set_buy_point(message: types.Message, regexp_command):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list(symbols)
        
        out = ""
        for symbol in symbol_split:
            symbol = symbol.strip().lower()
            p, _, _, btc_price = get_price(symbol)
            js = {}
            js["usd"] = p
            js["btc"] = btc_price
            r.set("At_" + symbol + "_" + message.from_user.mention, json.dumps(js))
            out = out + f"Gotit. {symbol} at ${round_sense(p)} or {round(btc_price,8)} BTC marked \n"
        
        await message.reply(out)
    except Exception as e:
        logging.error("BUY ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /buy btc')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['sell ([\s0-9.,a-zA-Z]*)']))
async def set_sell_point(message: types.Message, regexp_command):
    try:
        symbols = regexp_command.group(1)
        symbol_split = get_symbol_list(symbols)
        user = message.from_user.mention
        out = ""
        for symbol in symbol_split:
            symbol = symbol.strip().lower()
            p, _, _, btc_price = get_price(symbol)
            js = r.get("At_" + symbol + "_" + user).decode('utf-8')
            changes = 0
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
                out = out + f'Sold. {symbol} final diff in USD {changes}%  or in BTC {changes_btc} \n'
            r.delete("At_" + symbol + "_" + user)
            current_score = r.get("score_" + user)
            if current_score is None:
                current_score = 0
            else:
                current_score = float(current_score.decode('utf-8'))
            if changes == "NA":
                new_score = current_score
            else:
                new_score = current_score + changes
            new_score = str(round(new_score,2))
            out = out + f'Sold. {symbol} final diff in USD {changes}%  or in BTC {changes_btc} \n CURRENT SCORE = {new_score}'
            r.set("score_" + user, current_score + changes)
        await message.reply(out)
    except Exception as e:
        logging.error("Sell Error:" + str(e))
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
            await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Code Not Found. Try /watch aave')
        else:
            new_coin = new_coin.lower()
            if new_coin in config["watch_list"]:
                await message.reply(f'{message.from_user.first_name} Fail. Already Watching This One. ' + str(config["watch_list"]))
            else:
                config["watch_list"].append(new_coin)
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'Gotit. Added ' + new_coin)
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['watchalt ([a-zA-Z]*)']))
async def add_to_prices_alts(message: types.Message, regexp_command):
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
        if "watch_list_alts" not in config:
            config["watch_list_alts"] = []
        if a == 0:
            await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Code Not Found. Try /watchalt aave')
        else:
            new_coin = new_coin.lower()
            if new_coin in config["watch_list_alts"]:
                await message.reply(f'{message.from_user.first_name} Fail. Already Watching This One. ' + str(config["watch_list_alts"]))
            else:
                config["watch_list_alts"].append(new_coin)
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'Gotit. Added ' + new_coin)
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['remove ([a-zA-Z]*)']))
async def remove_from_prices(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1)
        logging.info("config")
        config = r.get(message.chat.id)
        if config is not None:
            config = json.loads(config)
            if "watch_list" in config:
                if new_coin in config["watch_list"]:
                    config["watch_list"].remove(new_coin)
                elif new_coin.lower() in config["watch_list"]:
                    config["watch_list"].remove(new_coin.lower())
                elif new_coin.upper() in config["watch_list"]:
                    config["watch_list"].remove(new_coin.upper())
                    
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'{message.from_user.first_name}, done. Removed ' + str(new_coin))
                return
                
        await message.reply(f'{message.from_user.first_name} Fail. Not found. ' + str(new_coin))
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['removealt ([a-zA-Z]*)']))
async def remove_from_prices_alts(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1)
        logging.info("config")
        config = r.get(message.chat.id)
        if config is not None:
            config = json.loads(config)
            if "watch_list_alts" in config:
                if new_coin in config["watch_list_alts"]:
                    config["watch_list_alts"].remove(new_coin)
                elif new_coin.lower() in config["watch_list_alts"]:
                    config["watch_list_alts"].remove(new_coin.lower())
                elif new_coin.upper() in config["watch_list_alts"]:
                    config["watch_list_alts"].remove(new_coin.upper())
                    
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'{message.from_user.first_name}, done. Removed ' + str(new_coin))
                return
                
        await message.reply(f'{message.from_user.first_name} Fail. Not found. ' + str(new_coin))
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
