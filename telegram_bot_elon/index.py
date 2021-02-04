import asyncio
import json
import requests
import os
from aiogram import Bot

# TOKEN var for elon_bot
TOKEN = os.environ["TELEGRAM_BOT"]

# def getUrl():
#     #obtain a json object with image details
#     #extract image url from the json object
#     contents = requests.get('https://api.thecatapi.com/v1/images/search')
#     js = contents.json()
#     print(js)
#     url = js[0]["url"]
#     return url

# def sendImage(update, context):
#     url = getUrl()
#     chat_id = update.message.chat_id
#     context.bot.send_photo(chat_id=chat_id, photo=url)

# def sendTable(update, context):
#     name = update.effective_user.first_name
#     if "josh" in name.lower():
#         update.message.reply_text(f'Hello {update.effective_user.first_name}, you are Jelly Hands')
#     else:
#         update.message.reply_text(f'Hello {update.effective_user.first_name}, you are HODLing strong')

# def prices(update, context):
#     chat_id = update.message.chat_id
#     mains = ["BTC", "ETH", "GRT", "LTC", "ADA", "AAVE", "DOGE"]
#     out = ""
#     totes = 0
#     for l in mains:
#         p, c = get_price(l)
#         totes = totes + c
#         context.bot.send_message(chat_id=chat_id, text=f"{l} ${round(p,4)} {round(c,1)}% 1 hour")
    
#     if totes<0:
#         context.bot.send_message(chat_id=chat_id, text="OUCH, NO LAMBO FOR YOU!")
#     elif totes>15:
#         context.bot.send_message(chat_id=chat_id, text="OK OK, LAMBO FOR YOU!")
#     else:
#         context.bot.send_message(chat_id=chat_id, text="MEH, MAYBE LAMBO. HODL.")

# def get_price(label):
#     price, change_1hr = 0, 0
#     logging.error("DOWNLOADING " + label)    
#     try:
#         url = "https://data.messari.io/api/v1/assets/" + label + "/metrics"
#         resp = requests.get(url)
#         js = resp.json()
#         price = js["data"]["market_data"]["price_usd"]
#         change_1hr = js["data"]["market_data"]["percent_change_usd_last_1_hour"]
#     except Exception as e:
#         logging.error(e)
#     return price, change_1hr

# def error_callback(bot, error):
#     logging.warning(str(error))


# updater = Updater(TOKEN)
# #call sendImage() when the user types a command in the telegram chat
# updater.dispatcher.add_handler(CommandHandler('doge',sendImage))
# updater.dispatcher.add_handler(CommandHandler('me',sendTable))
# updater.dispatcher.add_handler(CommandHandler('lambo',prices))
# updater.dispatcher.add_handler(CommandHandler('greendildos',prices))

# # Register it to the updater's dispatcher
# updater.dispatcher.add_error_handler(error_callback)

# #start the bot
# updater.start_polling()
# updater.idle()

async def start_handler(event: types.Message):
    await event.answer(
        f"Hello, {event.from_user.get_mention(as_html=True)} 👋!",
        parse_mode=types.ParseMode.HTML,
    )


async def main():
    bot = Bot(token=TOKEN)
    try:
        disp = Dispatcher(bot=bot)
        disp.register_message_handler(start_handler, commands={"cat", "dog"})
        await disp.start_polling()
    finally:
        await bot.close()

app = asyncio.run(main())