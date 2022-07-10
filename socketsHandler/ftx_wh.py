import hmac
import json
import time
import websocket
from pprint import pprint

from utils import notification
from exchanges import ftx_bot

from dotenv import dotenv_values
config = dotenv_values(".env")

class FtxWebsocketClient:
    def __init__(self):
        self.ws = None
        self._api_key = config['FTX_API_KEY']
        self._api_secret = config['FTX_API_SECRET']
        self._subaccount = config['FTX_SUBACCOUNT_NAME']

    def start(self):
        assert not self.ws, "ws should be closed before attempting to connect"

        self.ws = websocket.WebSocketApp(
            "wss://ftx.us/ws/",
            on_open=self._on_open,
            on_message=self._on_message,
            on_close=self._on_close,
            on_error=self._on_error,
        )

        self.ws.run_forever(ping_interval=15)

    def _on_open(self, ws):
        print("----OPEN----")
        ts = int(time.time() * 1000)
        self.ws.send(json.dumps({'op': 'login', 'args': {
            'key': self._api_key,
            'sign': hmac.new(
                self._api_secret.encode(), f'{ts}websocket_login'.encode(), 'sha256').hexdigest(),
            'time': ts,
            'subaccount': self._subaccount
        }}))

        self.ws.send(json.dumps(
            {'op': 'subscribe', 'channel': 'orders'}
        ))

    def _on_close(self, ws):
        print("----CLOSE----")
        self.ws.send(json.dumps(
            {'op': 'unsubscribe', 'channel': 'orders'}
        ))

    def _on_message(self, ws, raw_message: str):
        message = json.loads(raw_message)

        pprint(message)

        message_type = message['type']

        if message_type in {'subscribed', 'unsubscribed'}:
            return

        elif message_type == 'info':
            if message['code'] == 20001:
                print(message)
                return
        elif message_type == 'error':
            raise Exception(message)

        channel = message['channel']

        if channel == 'orders':

            data = message['data']

            pprint(data)

            if data['remainingSize'] == 0 and data['filledSize'] > 0:
                ticker = data['market']

                cur_bal = ftx_bot.get_balance_ticker(ticker)

                print(f"Current balance of {ticker} is {cur_bal}")

                if cur_bal == 0:
                    ftx_bot.reset_avg_price(ticker)

                if not ftx_bot.check_order(data['id']):
                    time.sleep(1)

                if ftx_bot.check_order(data['id']):

                    o = ftx_bot.get_order(data['id'])

                    if data['side'] == "buy":
                        avgbuyprice = ftx_bot.update_avg_price(ticker, price=data['avgFillPrice'],
                                                               amount=data['filledSize'])

                        ti = ftx_bot.get_ticker_info(ticker)

                        msg = {"type": "success", "exchange": "FTXUS", "symbol": ticker, "side": "buy",
                               "price": data['avgFillPrice'], "size": data['filledSize'],
                               "usd": data['filledSize'] * data['avgFillPrice'], "avgbuyprice": avgbuyprice}

                        notification.buy_filled(msg)

                        msgs = ftx_bot.reset_orders(ticker)
                        t = {"exchange": "FTXUS", "symbol": ticker, "data": msgs}
                        notification.reset_single_notification(t)

                    elif data['side'] == 'sell':

                        inf = ftx_bot.get_ticker_info(ticker)

                        msg = {"type": "success", "exchange": "FTXUS", "symbol": ticker, "side": "sell",
                               "size": data['filledSize'], "usd": data['filledSize'] * data['avgFillPrice'],
                               "avgbuyprice": inf['avg_price']}

                        notification.sell_filled(msg)

                        if o['reset']:
                            msgs = ftx_bot.reset_orders(ticker)
                            t = {"exchange": "FTXUS", "symbol": ticker, "data": msgs}
                            notification.reset_single_notification(t)

                    ftx_bot.delete_order(data['id'])

    def _on_error(self, ws, error):
        print("----ERROR----")
        pprint(error)



