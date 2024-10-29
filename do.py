''' Run a function by ado <func_name> '''


def set_hook():
    import asyncio
    from bot.settings import HEROKU_APP_NAME, WEBHOOK_URL, TELEGRAM_BOT
    from aiogram import Bot
    
    print('Setting Bot ' + TELEGRAM_BOT)
    bot = Bot(token=TELEGRAM_BOT)
    print('Set Bot ' + TELEGRAM_BOT)

    async def hook_set():
        if not HEROKU_APP_NAME:
            print('You have forgot to set HEROKU_APP_NAME')
            quit()
        print('Setting webhook ' + WEBHOOK_URL)
        await bot.set_webhook(WEBHOOK_URL)
        print('Set webhook ' + WEBHOOK_URL)
        print(await bot.get_webhook_info())
    

    asyncio.run(hook_set())
    bot.close()


def start():
    from bot.bot import main
    main()