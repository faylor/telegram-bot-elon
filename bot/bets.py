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
                          WEBAPP_HOST, WEBAPP_PORT, REDIS_URL, 
                          BETS_GAME_CHAT_ID, WALLET_GAME_CHAT_ID, SCORE_KEY, PRICES_IN)
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from collections import Counter

from .bot import dp, bot, r
from .user import add_win_for_user, add_random_prize_for_user, get_cards_remaining, get_user_prizes, clear_users_cards, clear_cards
from .prices import get_abs_difference, get_price
from .virtualwallet import get_users_live_value, get_parking, update_parking, user_spent_usd

BETS_KEY = "{chat_id}_bets"
BETS_KEY_LOCK = "{chat_id}_bets_lock"

async def weekly_tally(message: types.Message, r, show_all=False):
    p_btc, _, _, _ = get_price("btc")
    p_eth, _, _, _ = get_price("eth")
    out = "BTC Bets (Current=" + str(round(p_btc,0)) + "):\n"
    out = out + "<pre>Who             Bet      Diff\n"
    winning = ""
    winning_name = ""
    winning_eth_name = ""
    winning_diff = 99999
    cid = str(message.chat.id)
    ordered_btc = []
    btc_scores = []
    for key in r.scan_iter(f"{cid}_BTC_*"):
        a = r.get(key).decode('utf-8') or "NONE"
        d = get_abs_difference(a, p_btc)
        user_id = str(key.decode('utf-8')).replace(f"{cid}_BTC_","")
        if not user_id.isdigit():
            r.delete(key.decode('utf-8'))
            logging.error("User Id not stored in DB as int " + str(user_id) + " ignoring.")
        else:
            member = await bot.get_chat_member(message.chat.id, user_id)
            mention_name = member.user.mention
            if d <= winning_diff:
                if d == winning_diff:
                    winning = winning + ", " + user_id
                    winning_name = winning_name + ", " + mention_name
                else:
                    winning = user_id
                    winning_name = mention_name
                    winning_diff = d
            if len(ordered_btc) > 0:
                i = 0
                while i < len(btc_scores) and d > btc_scores[i]:
                    i = i + 1
                btc_scores.insert(i, d)
                if show_all:
                    ordered_btc.insert(i, mention_name.ljust(15, ' ') + " " + a.ljust(7, ' ') + "  " + str(round(d,1)))
                else:
                    ordered_btc.insert(i, mention_name.ljust(15, ' '))
            else:
                btc_scores.append(d)
                if show_all:
                    ordered_btc.append(mention_name.ljust(15, ' ') + " " + a.ljust(7, ' ') + "  " + str(round(d,1)))
                else:
                    ordered_btc.append(mention_name.ljust(15, ' '))
            
    out = out + "\n".join(ordered_btc)
    
    out = out + "</pre>\nWINNING BTC: " + winning_name + "\n"
    out = out + "\nETH Bets (Current=" + str(round(p_eth,0)) + "):\n"
    out = out + "<pre>Who             Bet     Diff\n"
    winning_eth = ""
    winning_diff = 99999
    ordered_eth = []
    eth_scores = []
    for key in r.scan_iter(f"{cid}_ETH_*"):
        a = r.get(key).decode('utf-8') or "NONE"
        d = get_abs_difference(a, p_eth)
        user_id = str(key.decode('utf-8')).replace(f"{cid}_ETH_","")
        if not user_id.isdigit():
            r.delete(key.decode('utf-8'))
            logging.error("User Id ETH not stored in DB as int " + str(user_id) + " ignoring.")
        else:
            member = await bot.get_chat_member(message.chat.id, user_id)
            mention_name = member.user.mention
            if d <= winning_diff:
                if d == winning_diff:
                    winning_eth = winning_eth + ", " + user_id
                    winning_eth_name = winning_eth_name + ", " + mention_name
                else:
                    winning_eth = user_id
                    winning_eth_name = mention_name
                    winning_diff = d
            if len(ordered_eth) > 0:
                i = 0
                while i < len(eth_scores) and d > eth_scores[i]:
                    i = i + 1
                eth_scores.insert(i, d)
                if show_all:
                    ordered_eth.insert(i, mention_name.ljust(15, ' ') + " " + a.ljust(7, ' ') + "  " + str(round(d,1)))
                else:
                    ordered_eth.insert(i, mention_name.ljust(15, ' '))
            else:
                eth_scores.append(d)
                if show_all:
                    ordered_eth.append(mention_name.ljust(15, ' ') + " " + a.ljust(7, ' ') + "  " + str(round(d,1)))
                else:
                    ordered_eth.append(mention_name.ljust(15, ' '))
            
    out = out + "\n".join(ordered_eth)
    out = out + "</pre>\nWINNING ETH: " + winning_eth_name + "\n"
    return out, winning, winning_eth, winning_name, winning_eth_name

@dp.message_handler(commands=['startbets', 'startweekly', 'startweeklybets', 'start#weeklybets'])
async def start_weekly(message: types.Message):
    cid = str(message.chat.id)
    for key in r.scan_iter(f"{cid}_BTC_*"):
        r.delete(key)
    for key in r.scan_iter(f"{cid}_ETH_*"):
        r.delete(key)
    unlock_bets(message.chat.id)
    await bot.send_message(chat_id=message.chat.id, text="DELETED BETS. Good Luck. [run /lockbets when everyone is ready]")

@dp.message_handler(commands=['bets', 'weekly', 'weeklybets', '#weeklybets'])
async def get_weekly(message: types.Message):
    locked = is_bets_locked(message.chat.id)
    logging.error(f"IS LOCKED {locked}")
    out, _, _, _, _ = await weekly_tally(message, r, show_all=locked)
    await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")

@dp.message_handler(commands=['lockbets'])
async def lock_bets(message: types.Message):
    lock_bets(message.chat.id)
    await bot.send_message(chat_id=message.chat.id, text="BETS LOCKED IN. Good Luck. [run /unlockbets if this was a mistake]")

@dp.message_handler(commands=['unlockbets'])
async def lock_bets(message: types.Message):
    logging.error("UNLOCKING....")
    unlock_bets(message.chat.id)
    logging.error("UNLOCKed....")
    await bot.send_message(chat_id=message.chat.id, text="BETS UNLOCKED. [run /lockbets if this was a mistake]")


@dp.message_handler(commands=['cards'])
async def show_cards(message: types.Message):
    try:
        uid = str(message.from_user.id)
        cards = get_user_prizes(uid, BETS_GAME_CHAT_ID)
        if BETS_GAME_CHAT_ID in cards and len(cards[BETS_GAME_CHAT_ID]) > 0:
            media = types.MediaGroup()
            counted_cards = Counter(cards[BETS_GAME_CHAT_ID])
            for card_name, counter in counted_cards.items():
                media.attach_photo(types.InputFile('assets/' + card_name + '.jpg'), str(counter) + ' x ' + card_name.upper())
            return await message.reply_media_group(media=media)
        else:
            return await message.reply(f'No POW cards... Win some bets')
    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text="PROBLEM GETTING PRIZE:" + str(e))

@dp.message_handler(commands=['deck'])
async def show_cards(message: types.Message):
    try:
        cid = str(message.chat.id)
        
        cards = get_cards_remaining(cid)
        media = types.MediaGroup()
        if 'cards' in cards:
            counted_cards = Counter(cards['cards'])
            if len(cards) > 0:
                for card_name, counter in counted_cards.items():
                    media.attach_photo(types.InputFile('assets/' + card_name + '.jpg'), str(counter) + ' x ' + card_name.upper())
                return await message.reply_media_group(media=media)
         
        return await message.reply(f'No POW cards... Win some bets')
            
    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text="PROBLEM GETTING DECK:" + str(e))


async def prize_message(chat_id, user_id, name, winning_card):
    try:
        if winning_card is None:
            return await bot.send_message(chat_id=chat_id, text=f'NO MORE POW CARDS LEFT :(')
        
        media = types.MediaGroup()
        media.attach_photo(types.InputFile('assets/' + winning_card + '.jpg'), 'CONGRATULATIONS ' + name)
        if winning_card == "ghost":
            await bot.send_media_group(chat_id=chat_id, media=media)
            return await bot.send_message(chat_id=chat_id, text="GHOST EXPIRES IN 24 HOURS, USE IT OR LOSE IT. " + name + "!!!")
        else:
            return await bot.send_media_group(chat_id=chat_id, media=media)
        
    except Exception as e:
        return await bot.send_message(chat_id=chat_id, text="PROBLEM GETTING PRIZE for " + name + " ... " + str(e))

@dp.message_handler(commands=['stopbets', 'stopweekly', 'stopweeklybets', 'stop#weeklybets'])
async def finish_weekly(message: types.Message):
    out, winning_btc, winning_eth, winning_name, winning_eth_name = await weekly_tally(message, r, show_all=True)
    await bot.send_message(chat_id=message.chat.id, text=out, parse_mode="HTML")
    await bot.send_message(chat_id=message.chat.id, text=f'BTC winner = {winning_name}, ETH winner = {winning_eth_name}')
    config = get_bets_totes(message.chat.id)
    if "," in winning_btc:
        winners = winning_btc.split(",")
        winning_names = winning_name.split(",")
        i = 0
        for winner in winners:
            winning_card = add_win_for_user(config, winner, message.chat.id)
            await prize_message(message.chat.id, winner, winning_names[i], winning_card)
            i = i + 1
    else:
        winning_card = add_win_for_user(config, winning_btc, message.chat.id)
        await prize_message(message.chat.id, winning_btc, winning_name, winning_card)
    if "," in winning_eth:
        winners = winning_eth.split(",")
        winning_eth_names = winning_eth_name.split(",")
        i = 0
        for winner in winners:
            winning_card = add_win_for_user(config, winner, message.chat.id)
            await prize_message(message.chat.id, winner, winning_eth_names[i], winning_card)
            i = i + 1
    else:
        winning_card = add_win_for_user(config, winning_eth, message.chat.id)
        await prize_message(message.chat.id, winning_eth, winning_eth_name, winning_card)
    
    logging.info(json.dumps(config))
    set_bets_totes(message.chat.id, config)
    await bot.send_message(chat_id=message.chat.id, text='To clear all bets for this week, run /startbets, and /lockbets to restrict bets')
    await total_weekly(message)

    last_user = get_wallet_last_place_user_id()
    if last_user is not None:
        member = await bot.get_chat_member(WALLET_GAME_CHAT_ID, last_user)
        parking = get_parking(WALLET_GAME_CHAT_ID)
        user_spent_usd(WALLET_GAME_CHAT_ID, last_user, -1 * parking, None, free_trades=True)
        update_parking(WALLET_GAME_CHAT_ID, -1 * parking)
        await bot.send_message(chat_id=message.chat.id, text=f"Last place WINNER! Receiving ${round(parking, 2)} free parking, you loser .... {member.user.mention}.")

        

def get_bets_totes(chat_id):
    bets_chat_key = BETS_KEY.format(chat_id=chat_id)
    config = r.get(bets_chat_key)
    if config is None:
        config = {"winners_list":[]}
    else:
        config = json.loads(config)
    return config

def unlock_bets(chat_id):
    bets_chat_key = BETS_KEY_LOCK.format(chat_id=chat_id)
    r.set(bets_chat_key, "False")
    logging.error(f"AFTER: {is_bets_locked(chat_id)}")

def lock_bets(chat_id):
    bets_chat_key = BETS_KEY_LOCK.format(chat_id=chat_id)
    r.set(bets_chat_key, "True")

def is_bets_locked(chat_id):
    bets_chat_key = BETS_KEY_LOCK.format(chat_id=chat_id)
    config = r.get(bets_chat_key)
    if config is None:
        r.set(bets_chat_key, "False")
        return False
    else:
        return bool(config)

def set_bets_totes(chat_id, config):
    bets_chat_key = BETS_KEY.format(chat_id=chat_id)
    r.set(bets_chat_key, json.dumps(config))

@dp.message_handler(commands=['leader', 'leaderboard', 'winning', 'totes'])
async def total_weekly(message: types.Message):
    try:
        config = get_bets_totes(message.chat.id)
        
        if "winners_list" in config:
            scores = [0]
            out = ["<pre>Who?            Wins"]
            for k, v in config["winners_list"].items():
                key = str(k)
                if key.isdigit():
                    chat_member = await bot.get_chat_member(message.chat.id, key)
                    name = chat_member.user.mention
                else:
                    name = key
                name = name.ljust(15,' ')
                if len(scores) == 1:
                    scores.append(float(v))
                    out.append(f"{name} {v}")
                else:
                    i = 1
                    score = float(v)
                    while i < len(scores) and score < scores[i]:
                        i = i + 1
                    out.insert(i, f"{name} {v}")
                    scores.insert(i, score)
            out.append("</pre>")
            s = "\n".join(out)
            await bot.send_message(chat_id=message.chat.id, text=s, parse_mode='HTML')
        else:
            await bot.send_message(chat_id=message.chat.id, text="No Winners Yet, bet first then stopbets... clown.")
    except Exception as e:
        await bot.send_message(chat_id=message.chat.id, text="Error wrong chat maybe, failed to find bets leaders?")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['bet btc ([0-9.,a-zA-Z]*) eth ([0-9.,a-zA-Z]*)']))
async def set_weekly(message: types.Message, regexp_command):
    try:
        if is_bets_locked(BETS_GAME_CHAT_ID):
            await message.reply(f'Bets are locked, cheating bastard.')   
        elif str(message.chat.id) != str(BETS_GAME_CHAT_ID):        
            amount = regexp_command.group(1)
            amount_eth = regexp_command.group(2)
            cid = str(BETS_GAME_CHAT_ID)
            r.set(f"{cid}_BTC_" + str(message.from_user.id), amount)
            r.set(f"{cid}_ETH_" + str(message.from_user.id), amount_eth)
            await message.reply(f'Gotit. Bet for first Mars seat: BTC {amount}, ETH {amount_eth}')
            await bot.send_message(chat_id=BETS_GAME_CHAT_ID, text=f"{message.from_user.mention} has bet.")
        else:
            await message.reply(f'Hide your bet, raise in private chat with me or whisper into your Tesla. I am always on.')
    except Exception as e:
        logging.error("Cannot bet: " + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /bet btc 12.3k eth 1.2k')

@dp.message_handler(commands=['clearbetstotals'])
async def clear_weekly_totals(message: types.Message):
    config = get_bets_totes(message.chat.id)
    if config is not None:
        config = json.loads(config)
        if "winners_list" in config:
            config["winners_list"] = {}
            set_bets_totes(message.chat.id, config)
            await bot.send_message(chat_id=message.chat.id, text='Cleared Table.')


def get_wallet_last_place_user_id():
    try:
        saves = r.scan_iter(SCORE_KEY.format(chat_id=WALLET_GAME_CHAT_ID, user_id="*"))
        scores = [0]
        users = []
        for key in saves:
            key = key.decode('utf-8')
            value = r.get(key)
            if "*" in key:
                r.delete(key)
            elif value is not None:
                value = value.decode('utf-8')
                user_id = key.replace(WALLET_GAME_CHAT_ID + "_bagscore_", "")
                js = json.loads(value)
                score_live = get_users_live_value(WALLET_GAME_CHAT_ID, user_id)
                score_usd = float(js[PRICES_IN.lower()])
                score_total = score_live + score_usd
                if len(scores) > 1:
                    i = 1
                    while i < len(scores) and score_total < scores[i]:
                        i = i + 1
                    users.insert(i, user_id)
                    scores.insert(i, score_total)
                else:
                    scores.append(score_total)
                    users.append(user_id)
        
        return users[-1]
    except Exception as e:
        logging.error("ERROR: " + str(e))
        return None, None

@dp.message_handler(commands=['setupagain'])
async def setup_totes_manually(message: types.Message):
    try:
        chat_id = message.chat.id
        # for key in r.scan_iter(f"{chat_id}_BTC_*"):
        #     user_id = str(key.decode('utf-8')).replace(f"{chat_id}_BTC_","")
        #     if not user_id.isdigit():
        #         logging.error("User Id not stored in DB as int " + str(user_id) + " ignoring.")
        #     else:
        #         member = await bot.get_chat_member(message.chat.id, user_id)
        #         mention_name = member.user.mention    
        #         logging.error(mention_name + " = " + user_id)
                
        set_user_total(chat_id, 1442973965, int(2))
        set_user_total(chat_id, 1038547988, int(3))
        set_user_total(chat_id, 1402645782, int(6))
        set_user_total(chat_id, 1597217560, int(3))
        set_user_total(chat_id, 1573604904, int(5))

        await total_weekly(message)
    except Exception as e:
        logging.error("Cannot bet: " + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. Try /bet btc 12.3k eth 1.2k')

def set_user_total(chat_id, user_id, total):
    try:
        logging.error("Current config set user total: " )
        
        config = get_bets_totes(chat_id)
        logging.error("Current config set user total: " + json.dumps(config))
        config["winners_list"][str(user_id)] = total
        
        set_bets_totes(chat_id, config)
    except Exception as e:
        logging.error("Cannot set user total: " + str(e))
        raise e
 
@dp.message_handler(commands=['add1'])
async def add_user(message: types.Message):
    logging.warn('user:' + str(message.from_user.id))
    config = r.get(message.chat.id)
    if config is None:
        config = {}
    else:
        config = json.loads(config)
    if "winners_list" not in config:
        config["winners_list"] = {}
    if str(message.from_user.id) not in config["winners_list"]:
        config["winners_list"][str(message.from_user.id)] = 1
    else:
        config["winners_list"][str(message.from_user.id)] = int(config["winners_list"][str(message.from_user.id)]) + 1
    logging.info(json.dumps(config))
    r.set(message.chat.id, json.dumps(config))
    await message.reply('user:' + message.from_user.mention)

@dp.message_handler(commands=['add2'])
async def add_user(message: types.Message):
    config = r.get(message.chat.id)
    if config is None:
        config = {}
    else:
        config = json.loads(config)
    if "winners_list" not in config:
        config["winners_list"] = {}
    if str(message.from_user.id) not in config["winners_list"]:
        config["winners_list"][str(message.from_user.id)] = 2
    else:
        config["winners_list"][str(message.from_user.id)] = int(config["winners_list"][str(message.from_user.id)]) + 2
    logging.info(json.dumps(config))
    r.set(message.chat.id, json.dumps(config))
    await message.reply('user:' + message.from_user.mention)

@dp.message_handler(commands=['add3'])
async def add_user(message: types.Message):
    config = r.get(message.chat.id)
    if config is None:
        config = {}
    else:
        config = json.loads(config)
    if "winners_list" not in config:
        config["winners_list"] = {}
    if str(message.from_user.id) not in config["winners_list"]:
        config["winners_list"][str(message.from_user.id)] = 3
    else:
        config["winners_list"][str(message.from_user.id)] = int(config["winners_list"][str(message.from_user.id)]) + 3
    logging.info(json.dumps(config))
    r.set(message.chat.id, json.dumps(config))
    await message.reply('user:' + message.from_user.mention)

@dp.message_handler(commands=['add4'])
async def add_user(message: types.Message):
    config = r.get(message.chat.id)
    if config is None:
        config = {}
    else:
        config = json.loads(config)
    if "winners_list" not in config:
        config["winners_list"] = {}
    if str(message.from_user.id) not in config["winners_list"]:
        config["winners_list"][str(message.from_user.id)] = 4
    else:
        config["winners_list"][str(message.from_user.id)] = int(config["winners_list"][str(message.from_user.id)]) + 4
    logging.info(json.dumps(config))
    r.set(message.chat.id, json.dumps(config))
    await message.reply('user:' + message.from_user.mention)

@dp.message_handler(commands=['minus1'])
async def minus_user(message: types.Message):
    config = r.get(message.chat.id)
    if config is not None:
        config = json.loads(config)
        if "winners_list" in config and str(message.from_user.id) in config["winners_list"]:
            config["winners_list"][str(message.from_user.id)] = int(config["winners_list"][str(message.from_user.id)]) - 1
            logging.info(json.dumps(config))
            r.set(message.chat.id, json.dumps(config))
    await message.reply('user:' + message.from_user.mention)
    
