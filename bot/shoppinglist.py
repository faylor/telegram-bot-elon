import logging
import json
from aiogram import types
from aiogram.dispatcher import filters
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

from .bot import dp, r, bot

class ShopForm(StatesGroup):
    item = State()


@dp.message_handler(commands=['pickup'])
async def pickup_list(message: types.Message):
    chat_id = message.chat.id
    mains = [""]
    try:
        config = json.loads(r.get(message.chat.id))
        logging.info(json.dumps(config))
        if "shop_list" in config:
            mains = config["shop_list"]
    except Exception as ex:
        logging.info("no config found, ignore")
    
    out = f"<pre>       Pickup\n"
    totes = 0

    
    for l in mains:
        l = l.ljust(25, ' ')
        out = out + f"{l} \n"
    out = out + "</pre>"
    await bot.send_message(chat_id=chat_id, text=out, parse_mode="HTML")

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['\+([\s0-9,.a-zA-Z]*)']))
async def add_to_shop(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1).strip()
        logging.info("config")
        config = r.get(message.chat.id)
        if config is None:
            config = {}
        else:
            config = json.loads(config)
        logging.info(json.dumps(config))
           
        if "shop_list" not in config:
            config["shop_list"] = []

        new_coin = new_coin.lower()
        if new_coin in config["shop_list"]:
            await message.reply(f'{message.from_user.first_name} Fail. Already Picked This One. ' + str(config["shop_list"]))
        else:
            config["shop_list"].append(new_coin)
            r.set(message.chat.id, json.dumps(config))
            await message.reply(f'Gotit. Added ' + new_coin)
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')

@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['\-([\s0-9,.a-zA-Z]*)']))
async def remove_from_shop(message: types.Message, regexp_command):
    try:
        new_coin = regexp_command.group(1).strip().lower()
        logging.info("config")
        config = r.get(message.chat.id)
        if config is not None:
            config = json.loads(config)
            if "shop_list" in config:
                if new_coin in config["shop_list"]:
                    config["shop_list"].remove(new_coin)
                    
                r.set(message.chat.id, json.dumps(config))
                await message.reply(f'{message.from_user.first_name}, done. You bought ' + str(new_coin))
                return
                
        await message.reply(f'{message.from_user.first_name} Fail. Not found. ' + str(new_coin))
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')

@dp.message_handler(commands=['shop'])
async def remove_from_shop_list(message: types.Message,  state: FSMContext):
    try:
        config = r.get(message.chat.id)
        if config is not None:
            config = json.loads(config)
            if "shop_list" in config:
                await ShopForm.item.set()
                
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
                markup.add(*config["shop_list"])
                markup.add("-- Done --")
                    
                return await message.reply(f"Buying:\n", reply_markup=markup)
   
        await message.reply(f'{message.from_user.first_name} No shopping found, try /+bananas etc..')
    except Exception as e:
        logging.warn(str(e))
        await message.reply(f'{message.from_user.first_name} Fail. You Idiot. ')


@dp.message_handler(lambda message: message.text in ["cancel", "Cancel", "-- Done --"], state=ShopForm.item)
async def cancel_spent(message: types.Message, state: FSMContext):
    await state.finish()
    markup = types.ReplyKeyboardRemove()
    return await message.reply("Done Shopping.", reply_markup=markup)

@dp.message_handler(state=ShopForm.item)
async def process_shop_list(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            item_bought_response = message.text.lower().strip()
            config = r.get(message.chat.id)
            if config is not None:
                config = json.loads(config)
                if "shop_list" in config:
                    if item_bought_response in config["shop_list"]:
                        config["shop_list"].remove(item_bought_response)
                        r.set(message.chat.id, json.dumps(config))

                        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
                        markup.add(*config["shop_list"])
                        markup.add("-- Done --")
                            
                        return await message.reply(f"Updated " + str(item_bought_response) + ":\n", reply_markup=markup)
                    else:
                        return await message.reply(f'{message.from_user.first_name}, not found.. ' + str(item_bought_response))
        # Finish conversation
        await state.finish()
    except Exception as e:
        logging.error("SHOP ERROR:" + str(e))
        await message.reply(f'{message.from_user.first_name} Fail. ' + str(e))
