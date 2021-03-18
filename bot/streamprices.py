import cryptowatch as cw
import os

class Crytream():

    def __init__(self) -> None:
        self.chat_ids = []
        cw.api_key = os.environ["CRYPTOWATCH_API"]
        cw.stream.subscriptions = ["assets:60:ohlc"]
        # cw.stream.on_trades_update = self.handle_trades_update
        cw.stream.on_intervals_update = self.handle_intervals_update
        self.bot = None

    
    def handle_intervals_update(self, interval_update):
        # market_msg = ">>> Market#{} Exchange#{} Pair#{}: {} New Trades".format(
        #     trade_update.marketUpdate.market.marketId,
        #     trade_update.marketUpdate.market.exchangeId,
        #     trade_update.marketUpdate.market.currencyPairId,
        #     len(trade_update.marketUpdate.tradesUpdate.trades),
        # )
        print(interval_update)
        # for interval in intervals_update.marketUpdate.intervalsUpdate.intervals:
        # if self.bot is not None:
        #     await self.bot.send_message(chat_id=self.chat_id[0], text=str(interval))
        #     # if interval.period == 60:
                # trade_msg = "Base:{} Quote:{}".format(
                #     interval.volumeBaseStr,
                #     interval.volumeQuoteStr
                # )
            
                # print(trade_msg)
    
    def add_chat_id(self, chat_id):
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)

    def remove_chat_id(self, chat_id):
        if chat_id in self.chat_ids:
            self.chat_ids.remove(chat_id)

    def start(self, bot):
        self.bot = bot
        cw.stream.connect()

    def stop(self):
        cw.stream.disconnect()