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
from .bot import dp, bot, r
from .user import add_win_for_user
from .prices import get_abs_difference, get_price

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

@dp.message_handler(commands=['clearbetstotals'])
async def clear_weekly_totals(message: types.Message):
    config = r.get(message.chat.id)
    if config is not None:
        config = json.loads(config)
        if "winners_list" in config:
            config["winners_list"] = {}
            r.set(message.chat.id, json.dumps(config))
            await bot.send_message(chat_id=message.chat.id, text='Cleared Table.')

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
