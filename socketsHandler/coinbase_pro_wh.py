import json
import time
import hashlib
import base64
import hmac
import websocket
from utils import notification

from pprint import pprint

from exchanges import coinbase_pro_bot

from dotenv import dotenv_values

config = dotenv_values(".env")


class CoinBaseProWebsocketClient():
    def __init__(self):
        self.ws = None
        self._api_key = config['COINBASE_KEY']
        self._api_secret = config['COINBASE_B64SECRET']
        self._api_passphrase = config['COINBASE_PASSPHRASE']
        self.url = "wss://ws-feed.pro.coinbase.com/"

    def start(self):
        assert not self.ws, "ws should be closed before attempting to connect"

        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_close=self._on_close,
            on_error=self._on_error
        )

        self.ws.run_forever(ping_interval=20)

    def _on_open(self, ws):
        print("----OPEN----")
        tickers = coinbase_pro_bot.get_all_ticker()

        prod = []

        for i in tickers:
            prod.append(i['ticker'])

        print(prod)

        timestamp = str(time.time())

        message = timestamp + 'GET' + '/users/self/verify'
        message = message.encode('ascii')
        hmac_key = base64.b64decode(self._api_secret)
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

        self.ws.send(json.dumps({
            "type": "subscribe",
            "product_ids": prod,
            "channels": ["user"],
            "signature": signature_b64,
            "key": self._api_key,
            "passphrase": self._api_passphrase,
            "timestamp": timestamp
        }))

    def _on_close(self, ws):
        print("----CLOSE----")

    def _on_error(self, ws, error):
        print("----ERROR----")
        pprint(error)

    def _on_message(self, ws, msg):

        data = json.loads(msg)

        if data['type'] == "done" and data['reason'] == "filled":

            pprint(data)

            ticker = data['product_id']

            cur_bal = coinbase_pro_bot.get_balance_ticker(ticker)

            print(f"Current balance of {ticker} is {cur_bal}")

            if cur_bal == 0:
                coinbase_pro_bot.reset_avg_price(ticker)

            if not coinbase_pro_bot.check_order(data['order_id']):
                time.sleep(1)

            if coinbase_pro_bot.check_order(data['order_id']):

                o = coinbase_pro_bot.get_order(data['order_id'])

                pprint(o)

                order_info = coinbase_pro_bot.get_order_info_api(data['order_id'])

                pprint(order_info)

                size = float(order_info['filled_size'])

                if order_info['type'] == "market":
                    price = float(order_info['funds']) / size
                else:
                    price = float(order_info['price'])

                if data['side'] == "buy":

                    print("calling update avg price")

                    avgbuyprice = coinbase_pro_bot.update_avg_price(ticker, price=price, amount=size)

                    msg = {"type": "success", "exchange": "COINBASEPRO", "symbol": ticker, "side": "buy",
                           "price": price, "size": size, "usd": price * size, "avgbuyprice": avgbuyprice}

                    notification.buy_filled(msg)

                    ti = coinbase_pro_bot.get_ticker_info(ticker)

                    pprint(ti)

                    msgs = coinbase_pro_bot.reset_orders(ticker)
                    t = {"exchange": "COINBASEPRO", "symbol": ticker, "data": msgs}
                    notification.reset_single_notification(t)

                elif data['side'] == 'sell':

                    inf = coinbase_pro_bot.get_ticker_info(ticker)

                    msg = {"type": "success", "exchange": "COINBASEPRO", "symbol": ticker, "side": "sell",
                           "size": size, "usd": order_info['executed_value'], "avgbuyprice": inf['avg_price']}

                    notification.sell_filled(msg)

                    if o['reset']:
                        msgs = coinbase_pro_bot.reset_orders(ticker)
                        t = {"exchange": "COINBASEPRO", "symbol": ticker, "data": msgs}
                        notification.reset_single_notification(t)

                coinbase_pro_bot.delete_order(data['order_id'])
