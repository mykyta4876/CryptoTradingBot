from pprint import pprint

import gemini
import requests
from pymongo import MongoClient

from dotenv import dotenv_values

config = dotenv_values(".env")

public_r = gemini.PublicClient()
r = gemini.PrivateClient(config['GEMINI_API_KEY'], config['GEMINI_API_SECRET'])

dbclient = MongoClient(config['MONGODB_URL'])
db = dbclient['tradingbot']
tickers_db = db["gemini_tickers"]
orders_db = db['gemini_orders']


# get balance of particular ticker
def get_balance_ticker(ticker):
    ticker = ticker.upper()
    ticker_first = ticker.replace('USD', '')

    balances = r.get_balance()
    curr_amount = 0
    for b in balances:
        if b['currency'] == ticker_first:
            curr_amount += float(b['available'])

    return curr_amount


# { nickname_ticker : "BTCUSD", // name which we will get from trading view
#   ticker : "BTCUSD", // realname which is used in the platform
#   avg_price : 123.21,
#   amount_per : 1,2,3,4,5,6 ,
#   profit_per : 5,10,15,20,25,30 ,
#   quan : 120 }

def check_order(orderid):
    o = orders_db.find_one({"order_id": str(orderid)})
    # pprint(o)

    if o is not None:
        return True
    else:
        return False


def delete_order(orderid):
    orders_db.delete_one({"order_id": str(orderid)})


def get_order(orderid):
    o = orders_db.find_one({"order_id": str(orderid)})

    return o


def get_all_orders():
    o = orders_db.find({})

    return o


def add_order(orderid, reset=True):
    data = {"order_id": orderid, "reset": reset}
    ir = orders_db.insert_one(data)

    return ir


def check_ticker_by_nickname(nickname):
    sy = tickers_db.find_one({"nickname_ticker": nickname.upper()})

    return sy is not None


def get_ticker_info_by_nickname(nickname):
    sy = tickers_db.find_one({"nickname_ticker": nickname.upper()})

    return sy


def check_ticker(ticker):
    sy = tickers_db.find_one({"ticker": ticker.upper()})

    return sy is not None


def get_ticker_info(ticker):
    sy = tickers_db.find_one({"ticker": ticker.upper()})

    return sy


def reset_avg_price(ticker):
    tickers_db.update_one({
        "ticker": ticker.upper()
    }, {
        '$set': {
            'avg_price': 0
        }
    }, upsert=False)


def update_avg_price(ticker, price, amount):
    price = float(price)
    amount = float(amount)

    sy = get_ticker_info(ticker)
    old_amount = get_balance_ticker(ticker) - amount

    print(f"update avg price -> old_amount = {old_amount} ")

    new_quan = old_amount + amount
    new_avg_price = ((float(sy['avg_price']) * old_amount) + price * amount) / new_quan

    new_avg_price = float("{0:.3f}".format(new_avg_price))

    tickers_db.update_one({
        "ticker": ticker.upper()
    }, {
        '$set': {
            'avg_price': new_avg_price
        }
    }, upsert=False)

    return float(new_avg_price)


def get_usd_balance():
    balances = r.get_balance()
    curr_amount = 0

    for b in balances:
        if b['currency'] == 'USD':
            curr_amount += float(b['available'])

    return curr_amount


def get_precision(num):
    price_order = 0
    while float(num) * 10 ** price_order % 1 != 0:
        price_order += 1

    return int(price_order)


def get_symbol_details(ticker):
    base_url = "https://api.gemini.com/v1"
    response = requests.get(base_url + f"/symbols/details/{ticker}")
    symbols = response.json()

    return symbols


# cancel open order of particular ticker
def cancel_orders(ticker):
    all_orders = r.active_orders()
    cp = 0
    for o in all_orders:
        if o['symbol'] == ticker.lower():
            cp = 1
            r.cancel_order(o['order_id'])

    if cp > 0:
        msg = {"type": "success", "exchange": "GEMINI", "symbol": ticker,
               "success": f"All Open orders are successfully cancelled. "}

        return msg
    else:
        msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker,
               "error": f"There are no orders to cancel."}

        return msg


def check_sell_order(ticker):
    all_orders = r.active_orders()
    for o in all_orders:
        if o['symbol'] == ticker.lower() and o['side'] == 'sell':
            return True

    return False


# reset particular ticker
def reset_orders(ticker):
    all_orders = r.active_orders()
    for o in all_orders:
        if o['symbol'] == ticker.lower() and o['side'] == 'sell':
            r.cancel_order(o['order_id'])

    amount = get_balance_ticker(ticker)

    print("resetting amount - ", amount)

    if amount > 0:
        ticker_in = public_r.get_ticker(ticker)
        new_price = float(ticker_in['last'])

        ticker_info = get_ticker_info(ticker)
        avg_buy_price = float(ticker_info['avg_price'])

        if avg_buy_price > new_price:
            new_price = avg_buy_price

        return sell_pattern(ticker, amount, new_price)

    else:
        msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker,
               "error": f"There are no existing position to reset."}

        return msg


# sell particular ticker
def sell_pattern(ticker, amount, price):
    price = float(price)
    amount = float(amount)

    ticker_info = get_ticker_info(ticker)

    det = get_symbol_details(ticker)
    price_pre = get_precision(det['quote_increment'])
    amount_pre = get_precision(det['tick_size'])

    amount_per = ticker_info['amount_per'].split(',')
    profit_per = ticker_info['profit_per'].split(',')

    orders = []
    msgs = []

    for i in range(0, len(amount_per)):
        new_amount = (float(amount_per[i]) / 100) * amount
        new_amount = round(new_amount, amount_pre)

        new_price = (100 + float(profit_per[i])) * (price / 100.00)
        new_price = round(new_price, price_pre)

        if new_amount >= float(det['min_order_size']):
            o = r.new_order(symbol=ticker, amount=str(new_amount), price=str(new_price),
                            side="sell", options=[])

            amount = amount - new_amount
            orders.append(o)

            msg = {"type": "success", "exchange": "GEMINI", "price": o["price"], "size": o['original_amount'],
                   "symbol": ticker, 'ordertype': "limit"}

            msgs.append(msg)

        else:
            break

    pprint(orders)
    return msgs


def sell(ticker, amount, price, reset=True):
    price = float(price)
    amount = float(amount)

    det = get_symbol_details(ticker)
    price_pre = get_precision(det['quote_increment'])
    amount_pre = get_precision(det['tick_size'])

    amount = round(amount, amount_pre)
    price = round(price, price_pre)

    if amount >= float(det['min_order_size']):
        o = r.new_order(symbol=ticker, amount=str(amount), price=str(price),
                        side="sell", options=[])

        pprint(o)

        add_order(o['order_id'], reset)

        msg = {"type": "success", "exchange": "GEMINI", "price": o["price"], "size": o['original_amount'],
               "side": "sell",
               "symbol": ticker, 'ordertype': "limit"}

    else:
        msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker, "side": "sell",
               "error": f"You are trying to sell {amount} which is less than minimum allowed {det['min_order_size']}"}

    return msg


def buy(ticker, usd, price, ordertype="limit", reset=True):
    price = float(price)
    usd = float(usd)

    det = get_symbol_details(ticker)
    price_pre = get_precision(det['quote_increment'])
    amount_pre = get_precision(det['tick_size'])

    baln = get_usd_balance()

    if usd > baln:
        msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker, "side": "buy",
               "error": f"You have balance of {baln} but you are trying to buy for {usd}"}

        return msg

    if ordertype == "limit":

        price = float(price)
        price = round(price, price_pre)

        amount = float(usd / price)
        amount = round(amount, amount_pre)

        if amount >= float(det['min_order_size']):
            o = r.new_order(symbol=ticker, amount=str(amount), price=str(price), side="buy", options=[])
            msg = {"type": "success", "exchange": "GEMINI", "price": o['price'], "size": o['original_amount'],
                   "symbol": ticker, 'ordertype': "limit", "side": "buy"}
        else:
            o = None
            msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker, "side": "buy",
                   "error": f"You are trying to buy {amount} which is less than minimum allowed {det['min_order_size']}"}
    else:
        ticker_in = public_r.get_ticker(ticker)
        last_price = float(ticker_in['last'])

        price = float(3 * last_price)
        price = round(price, price_pre)

        amount = float(usd / price)
        amount = round(amount, amount_pre)

        if amount >= float(det['min_order_size']):
            o = r.new_order(symbol=ticker.lower(), amount=str(amount), price=str(price), side="buy", options=[])
            msg = {"type": "success", "exchange": "GEMINI", "price": last_price, "size": o['original_amount'],
                   "symbol": ticker, 'ordertype': "market", "side": "buy"}
        else:
            o = None
            msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker,
                   "error": f"You are trying to buy {amount} which is less than minimum allowed {det['min_order_size']}",
                   "side": "buy"}

    if o is not None:
        pprint(o)
        add_order(o['order_id'], reset)

    return msg
