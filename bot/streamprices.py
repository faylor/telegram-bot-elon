import cryptowatch as cw
import os

class Crytream():

    def __init__(self) -> None:
        self.chat_ids = []
        cw.api_key = os.environ["CRYPTOWATCH_API"]
        cw.stream.subscriptions = ["assets:60:ohlc"]
        cw.stream.on_trades_update = self.handle_trades_update
    
    def handle_trades_update(self, trade_update):
        market_msg = ">>> Market#{} Exchange#{} Pair#{}: {} New Trades".format(
            trade_update.marketUpdate.market.marketId,
            trade_update.marketUpdate.market.exchangeId,
            trade_update.marketUpdate.market.currencyPairId,
            len(trade_update.marketUpdate.tradesUpdate.trades),
        )
        print(market_msg)
        for trade in trade_update.marketUpdate.intervalsUpdate.intervals:
            if trade.period == 60:
                trade_msg = "\tOpen:{} High:{} Low:{} Close:{}".format(
                    trade.ohlc.openStr,
                    trade.ohlc.highStr,
                    trade.ohlc.lowStr,
                    trade.ohlc.closeStr
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