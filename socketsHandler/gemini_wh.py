import base64
import hashlib
import hmac
import json
import ssl
import time
from pprint import pprint

import websocket

from utils import notification
from exchanges import gemini_bot

from dotenv import dotenv_values
config = dotenv_values(".env")


class GeminiWebsocketClient:
    def __init__(self):
        self.ws = None
        self._api_key = config['GEMINI_API_KEY']
        self._api_secret = config['GEMINI_API_SECRET']

    def start(self):
        assert not self.ws, "ws should be closed before attempting to connect"

        payload = {"request": "/v1/order/events", "nonce": int(time.time() * 1000)}
        encoded_payload = json.dumps(payload).encode()
        b64 = base64.b64encode(encoded_payload)

        signature = hmac.new(bytes(self._api_secret, 'latin-1'), b64, hashlib.sha384).hexdigest()

        link =  "wss://api.gemini.com/v1/order/events?eventTypeFilter=closed"
        # link = "wss://api.sandbox.gemini.com/v1/order/events?eventTypeFilter=closed"

        self.ws = websocket.WebSocketApp(
            link,
            on_open=self._on_open,
            on_message=self._on_message,
            header={
                'X-GEMINI-PAYLOAD': b64.decode(),
                'X-GEMINI-APIKEY': self._api_key,
                'X-GEMINI-SIGNATURE': signature,
            },
            on_close=self._on_close,
            on_error=self._on_error
        )

        self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_interval=10)

    def _on_open(self, ws):
        print("----OPEN----")
        print(gemini_bot.orders_db.name)
        time.sleep(5)

    def _on_close(self, ws):
        print("----CLOSE----")

    def _on_message(self, ws, raw_message: str):
        if raw_message[0] != '[':
            message = json.loads(raw_message)
        else:
            s = raw_message[1:-1]
            s = json.loads(s)
            message = s

        if message['type'] == 'subscription_ack':
            print(message)
            return

        if message['type'] == "heartbeat":
            return

        t = message

        ticker = t['symbol']

        order_id = t['order_id']

        print(order_id)

        cur_bal = gemini_bot.get_balance_ticker(ticker)

        print(f"Current balance of {ticker} is {cur_bal}")

        if cur_bal == 0:
            gemini_bot.reset_orders(ticker)

        if not gemini_bot.check_order(order_id):
            time.sleep(1)

        if gemini_bot.check_order(order_id):

            pprint("order found")

            pprint(t)


            o = gemini_bot.get_order(order_id)

            print(o)

            if t['side'] == "buy":
                print("runnig buy side")
                avgbuyprice = gemini_bot.update_avg_price(ticker, price=t['avg_execution_price'],
                                                          amount=t['executed_amount'])

                print("new avg buy price - ", avgbuyprice)

                msg = {"type": "success", "exchange": "GEMINI", "symbol": ticker, "side": "buy",
                       "price": t['avg_execution_price'], "size": t['executed_amount'],
                       "usd": float(float(t['executed_amount']) * float(t['avg_execution_price'])), "avgbuyprice": avgbuyprice}

                pprint(msg)

                notification.buy_filled(msg)

                ti = gemini_bot.get_ticker_info(ticker)
                pprint(ti)

                msgs = gemini_bot.reset_orders(ticker)
                rst = {"exchange": "GEMINI", "symbol": ticker, "data": msgs}
                notification.reset_single_notification(rst)

            elif t['side'] == 'sell':

                inf = gemini_bot.get_ticker_info(ticker)

                msg = {"type": "success", "exchange": "GEMINI", "symbol": ticker, "side": "sell",
                       "size": t['executed_amount'], "usd": float(float(t['executed_amount']) * float(t['avg_execution_price'])),
                       "avgbuyprice": inf['avg_price']}

                notification.sell_filled(msg)

                if o['reset']:
                    msgs = gemini_bot.reset_orders(ticker)
                    rst = {"exchange": "GEMINI", "symbol": ticker, "data": msgs}
                    notification.reset_single_notification(rst)

            gemini_bot.delete_order(order_id)

        # else:
            # pprint(gemini_bot.get_order(t['order_id']))
            # t = gemini_bot.get_all_orders()
            # for x in t:
            #     print(x['order_id'])

    def _on_error(self, ws, error):
        print("----ERROR----")
        pprint(error)

