import logging
import json
import requests
import redis
import asyncio
import random
from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher, filters
from aiogram.utils.executor import start_webhook
from aiogram.dispatcher.webhook import SendMessage
from aiogram.utils.markdown import escape_md
from bot.settings import (TELEGRAM_BOT, HEROKU_APP_NAME,
                          WEBHOOK_URL, WEBHOOK_PATH,
                          WEBAPP_HOST, WEBAPP_PORT, REDIS_URL)
from .bot import r, dp

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

def get_user_price_config(user):
    try:
        config = r.get("prices_" + user)
        if config is None:
            return "usd"
        else:
            return config.decode('UTF-8')
    except Exception as e:
        return "usd"

def add_win_for_user(config, user_id, chat_id):
    if len(user_id.strip()) > 0:
        user_id = str(user_id)
        if user_id not in config["winners_list"]:
            config["winners_list"][user_id] = 1
        else:
            config["winners_list"][user_id] = int(config["winners_list"][user_id]) + 1
        #add_random_prize_for_user(user_id, chat_id)

def add_random_prize_for_user(user_id, chat_id):
    if len(user_id.strip()) > 0:
        config = r.get("cards_" + user)
        choice = select_card(chat_id)
        if config is None:
            r.set("cards_" + user, json.dumps({chat_id: [choice]}))
        else:
            cards = json.loads(config)
            if chat_id in cards:
                cards[chat_id] = cards.append(choice)
            else:
                cards.append({chat_id: [choice]})
            r.set("cards_" + user, json.dumps(cards))

def get_user_prizes(user_id, chat_id):
    cards = []
    if len(user_id.strip()) > 0:
        config = r.get("cards_" + user)
        if config is not None:
            cards = json.loads(config)
    return cards

def setup_cards(chat_id, red_shells = 6, ghost_cards = 3, trade_tokens = 23):
    cards = ['red_shell'] * red_shells
    cards = cards.extend(['ghost'] * ghost_cards)
    cards = cards.extend(['trade_token'] * trade_tokens)
    config = r.set("chat_cards_" + str(chat_id), json.dumps(cards))

def select_card(chat_id):
    cards = json.loads(r.get("chat_cards_" + str(chat_id)))
    if cards is None:
        setup_cards()
        cards = json.loads(r.get("chat_cards_" + str(chat_id)))
        if cards is None:
            raise Exception("Cannot create card set...")
    choice = random.choice(cards)
    cards.remove(choice)
    config = r.set("chat_cards_" + str(chat_id), json.dumps(cards))
    return choice

    
    
    
