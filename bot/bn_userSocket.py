from binance.client import Client
from binance import *
from twisted.internet import reactor
import threading

class bn_UserSocket(BinanceSocketManager):
    def start_user_socket(self, callback):
        # Get the user listen key
        user_listen_key = self._client.stream_get_listen_key()
        # and start the socket with this specific key
        return self._start_account_socket('userData', user_listen_key, callback)