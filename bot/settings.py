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


TWITTER_CONSUMER_KEY = os.environ.get("TWITTER_CONSUMER_KEY")
TWITTER_CONSUMER_SECRET = os.environ.get("TWITTER_CONSUMER_SECRET")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

BN_API_KEY = os.environ.get("BN_API")
BN_API_SECRET = os.environ.get("BN_SECRET")
BN_TEST_API_KEY = os.environ.get("BN_TEST_API")
BN_TEST_API_SECRET = os.environ.get("BN_TEST_SECRET")
BN_CHAT_ID = os.environ.get("BN_CHAT_ID")
BN_CHAT_ID_GROUP = os.environ.get("BN_CHAT_ID_GROUP")

OPENAI = os.environ.get("OPENAI")

BETS_GAME_CHAT_ID = os.environ.get("BETS_GAME_CHAT_ID")
WALLET_GAME_CHAT_ID = os.environ.get("WALLET_GAME_CHAT_ID")

SCORE_KEY = "{chat_id}_bagscore_{user_id}"
STAR_KEY = "{chat_id}_star_{user_id}"
SCORE_LOG_KEY = "{chat_id}_baglog_{user_id}"
TRADE_LOCK_KEY = "{chat_id}_baglock_{user_id}"
PRICES_IN = "USDT"
MAX_TRADES = 125
FEE = 0.0022