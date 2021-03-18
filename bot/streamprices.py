import cryptowatch as cw
import os

class Crytream():

    def __init__(self) -> None:
        self.chat_ids = []
        cw.api_key = os.environ["CRYPTOWATCH_API"]
        cw.stream.subscriptions = ["markets:*:trades"]
        cw.stream.on_trades_update = self.handle_trades_update
    
    def handle_trades_update(self, trade_update):
        market_msg = ">>> Market#{} Exchange#{} Pair#{}: {} New Trades".format(
            trade_update.marketUpdate.market.marketId,
            trade_update.marketUpdate.market.exchangeId,
            trade_update.marketUpdate.market.currencyPairId,
            len(trade_update.marketUpdate.tradesUpdate.trades),
        )
        print(market_msg)
        for trade in trade_update.marketUpdate.tradesUpdate.trades:
            trade_msg = "\tID:{} TIMESTAMP:{} TIMESTAMPNANO:{} PRICE:{} AMOUNT:{}".format(
                trade.externalId,
                trade.timestamp,
                trade.timestampNano,
                trade.priceStr,
                trade.amountStr,
            )
            print(trade_msg)
    
    def add_chat_id(self, chat_id):
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)

    def remove_chat_id(self, chat_id):
        if chat_id in self.chat_ids:
            self.chat_ids.remove(chat_id)

    def start(self):
        cw.stream.connect()

    def stop(self):
        cw.stream.disconnect()