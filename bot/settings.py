import os


TELEGRAM_BOT = os.getenv('TELEGRAM_BOT')
if not TELEGRAM_BOT:
    print('You have forgot to set TELEGRAM_BOT')
    quit()

HEROKU_APP_NAME = os.getenv('HEROKU_APP_NAME')


# webhook settings
WEBHOOK_HOST = f'https://{HEROKU_APP_NAME}.herokuapp.com'
WEBHOOK_PATH = f'/webhook/{TELEGRAM_BOT}'
WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}'

# webserver settings
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = int(os.getenv('PORT'))

REDIS_URL = os.environ.get("REDIS_URL")