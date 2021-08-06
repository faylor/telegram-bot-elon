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
            if config["winners_list"] == []:
                config["winners_list"] = {user_id: 1}
            else:
                config["winners_list"][user_id] = 1
        else:
            config["winners_list"][user_id] = int(config["winners_list"][user_id]) + 1
        return add_random_prize_for_user(user_id, chat_id)
    return None

def add_random_prize_for_user(user_id, chat_id):
    if len(user_id.strip()) > 0:
        config = r.get("cards_" + str(user_id))
        choice = select_card(chat_id)
        if choice is None:
            return None
        elif config is None:
            r.set("cards_" + str(user_id), json.dumps({chat_id: [choice]}))
        else:
            cards = json.loads(config)
            if chat_id in cards and cards[chat_id] is not None:
                cards[chat_id] = cards[chat_id] + [choice]
            else:
                cards[chat_id] = [choice]
            r.set("cards_" + str(user_id), json.dumps(cards))
        return choice

def delete_card(user_id, chat_id, card):
    config = r.get("cards_" + str(user_id))
    if card is None or config is None:
        return None
    else:
        user_cards = json.loads(config)
        if chat_id in user_cards and user_cards[chat_id] is not None:
            user_cards[chat_id].remove(card)
            r.set("cards_" + str(user_id), json.dumps(user_cards))
            return "DELETED"
    return "OK"

def get_user_prizes(user_id, chat_id):
    cards = []
    if len(user_id.strip()) > 0:
        config = r.get("cards_" + str(user_id))
        if config is not None:
            cards = json.loads(config)
    return cards

def setup_cards(chat_id, red_shells = 10, ghost_cards = 4, trade_tokens = 23):
    print("Setup Deck of Cards..")
    cards = []
    cards = cards + (['red_shell'] * red_shells)
    cards = cards + (['ghost'] * ghost_cards)
    cards = cards + (['trade_token'] * trade_tokens)
    print(str(cards))
    config = r.set("chat_cards_" + str(chat_id), json.dumps({"cards": cards}))

def select_card(chat_id):
    print("Select Card..")
    cards = r.get("chat_cards_" + str(chat_id))
    print("Got Card.." + str(cards))
    if cards is None:
        setup_cards(chat_id)
        cards = r.get("chat_cards_" + str(chat_id))
        if cards is None:
            raise Exception("Cannot create card set...")
    cards = json.loads(cards)
    print("Got Card2.." + str(cards))
    if len(cards["cards"]) == 0:
        print("Got Card Empty.." + str(cards))
        return None
    else:
        choice = random.choice(cards["cards"])
        cards["cards"].remove(choice)
        config = r.set("chat_cards_" + str(chat_id), json.dumps(cards))
        print("Selected Card.." + choice)
        return choice

def get_cards_remaining(chat_id):
    cards = r.get("chat_cards_" + str(chat_id))
    if cards is None:
        return []
    cards = json.loads(cards)
    return cards

def clear_cards(chat_id):
    r.delete("chat_cards_" + str(chat_id))

def clear_users_cards(user_id):
    r.delete("cards_" + str(user_id))
    
    
    
    
