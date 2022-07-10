from pprint import pprint

import cbpro
from pymongo import MongoClient
from dotenv import dotenv_values

config = dotenv_values(".env")

public_client = cbpro.PublicClient()
client = cbpro.AuthenticatedClient(config['COINBASE_KEY'], config['COINBASE_B64SECRET'], config['COINBASE_PASSPHRASE'])

dbclient = MongoClient(config['MONGODB_URL'])
db = dbclient['tradingbot']
tickers_db = db["cbp_tickers"]
orders_db = db['cbp_orders']


# get balance of particular ticker
def get_balance_ticker(ticker):
    tf = ticker.split('-')[0]
    acc = client.get_accounts()
    cur_amount = 0
    for a in acc:
        if a['currency'] == tf:
            cur_amount = float(a['available'])

    return cur_amount


# { nickname_ticker : "BTCUSD", // name which we will get from trading view
#   ticker : "BTCUSD", // realname which is used in the platform
#   avg_price : 123.21,
#   amount_per : 1,2,3,4,5,6 ,
#   profit_per : 5,10,15,20,25,30 ,
#   quan : 120}

def check_ticker_by_nickname(nickname):
    sy = tickers_db.find_one({"nickname_ticker": nickname.upper()})

    return sy is not None


def get_ticker_info_by_nickname(nickname):
    sy = tickers_db.find_one({"nickname_ticker": nickname.upper()})

    return sy


def check_ticker(ticker):
    sy = tickers_db.find_one({"ticker": ticker.upper()})

    return sy is not None


def get_all_ticker():
    sy = tickers_db.find({})

    return sy


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


def check_order(orderid):
    o = orders_db.find_one({"order_id": orderid})

    if o is not None:
        return True
    else:
        return False


def get_order(orderid):
    o = orders_db.find_one({"order_id": orderid})

    return o


def add_order(orderid, reset=True):
    data = {"order_id": orderid, "reset": reset}
    ir = orders_db.insert_one(data)

    return ir


def get_precision(num):
    price_order = 0
    while float(num) * 10 ** price_order % 1 != 0:
        price_order += 1

    return int(price_order)


def get_usd_balance():
    acc = client.get_accounts()
    cur_amount = 0
    for a in acc:
        if a['currency'] == 'USD':
            cur_amount = float(a['available'])

    return cur_amount


def get_symbol_details(ticker):
    t = client.get_products()
    # ticker_first = ticker.replace('-USD', '')
    for x in t:
        if x['id'] == ticker.upper():
            return x

    return None


def get_order_info_api(order_id):
    o = client.get_order(order_id)

    return o


def delete_order(orderid):
    orders_db.delete_one({"order_id": str(orderid)})


# cancel open order of particular ticker
def cancel_orders(ticker):
    all_orders = client.get_orders(product_id=ticker)
    cp = 0

    for o in all_orders:
        cp = 1
        break

    if cp > 0:
        t = client.cancel_all(product_id=ticker)
        msg = {"type": "success", "exchange": "COINBASEPRO", "symbol": ticker,
               "success": f"All Open orders are successfully cancelled. "}

        return msg
    else:
        msg = {"type": "error", "exchange": "COINBASEPRO", "symbol": ticker,
               "error": f"There are no orders to cancel."}

        return msg


def check_sell_order(ticker):
    all_orders = client.get_orders(product_id=ticker)
    for o in all_orders:
        if o['product_id'] == ticker and o['side'] == 'sell':
            return True

    return False


# reset particular ticker
def reset_orders(ticker):
    all_orders = client.get_orders(product_id=ticker)

    for o in all_orders:
        if o['product_id'] == ticker and o['side'] == 'sell':
            client.cancel_order(o['id'])

    amount = get_balance_ticker(ticker)

    print("resetting amount - ", amount)

    if amount > 0:

        ticker_in = public_client.get_product_ticker(product_id=ticker)
        new_price = float(ticker_in['price'])

        ticker_info = get_ticker_info(ticker)
        avg_buy_price = float(ticker_info['avg_price'])

        if avg_buy_price > new_price:
            new_price = avg_buy_price

        return sell_pattern(ticker, amount, new_price)

    else:
        msg = {"type": "error", "exchange": "COINBASEPRO", "symbol": ticker,
               "error": f"There are no existing position to reset."}

        return msg


def sell_pattern(ticker, amount, price):
    price = float(price)
    amount = float(amount)

    ticker_info = get_ticker_info(ticker)

    det = get_symbol_details(ticker)
    price_pre = get_precision(det['quote_increment'])
    amount_pre = get_precision(det['base_min_size'])

    amount_per = ticker_info['amount_per'].split(',')
    profit_per = ticker_info['profit_per'].split(',')

    orders = []
    msgs = []
    for i in range(0, len(amount_per)):
        new_amount = (float(amount_per[i]) / 100) * amount
        new_amount = round(new_amount, amount_pre)

        new_price = (100 + float(profit_per[i])) * (price / 100.00)
        new_price = round(new_price, price_pre)

        if new_amount >= float(det['base_min_size']):
            o = client.sell(product_id=ticker, size=new_amount,
                            price=new_price,
                            order_type='limit')

            amount = amount - new_amount
            orders.append(o)

            msg = {"type": "success", "exchange": "COINBASEPRO", "price": o['price'], "size": o['size'],
                   "symbol": ticker, 'ordertype': "limit"}

            msgs.append(msg)

        else:
            break

    pprint(orders)

    return msgs


# sell particular ticker
def sell(ticker, amount, price, reset=True):
    price = float(price)
    amount = float(amount)

    det = get_symbol_details(ticker)
    price_pre = get_precision(det['quote_increment'])
    amount_pre = get_precision(det['base_min_size'])

    amount = round(amount, amount_pre)
    price = round(price, price_pre)

    if amount >= float(det['base_min_size']):
        o = client.sell(product_id=ticker, size=amount, price=price, order_type='limit')
        pprint(o)

        add_order(o['id'], reset)

        msg = {"type": "success", "exchange": "COINBASEPRO", "price": o['price'], "size": o['size'], "side": "sell",
               "symbol": ticker, 'ordertype': "limit"}
    else:
        msg = {"type": "error", "exchange": "COINBASEPRO", "symbol": ticker, "side": "sell",
               "error": f"You are trying to sell {amount} which is less than minimum allowed {det['base_min_size']}"}

    return msg


def buy(ticker, usd, price=0, ordertype="limit", reset=True):
    price = float(price)
    usd = float(usd)

    det = get_symbol_details(ticker)
    price_pre = get_precision(det['quote_increment'])
    amount_pre = get_precision(det['base_min_size'])

    baln = get_usd_balance()

    if usd > baln:
        msg = {"type": "error", "exchange": "COINBASEPRO", "symbol": ticker, "side": "buy",
               "error": f"You have balance of {baln} but you are trying to buy for {usd}"}

        return msg

    if ordertype == "limit":
        amount = float(usd / price)
        # print(amount)
        # print(maxpr)
        amount = round(amount, amount_pre)
        # pprint(amount)
        price = round(price, price_pre)
        if float(amount) >= float(det['base_min_size']):
            # print("running limit coinbase pro bot buy")
            # print(float(det['min_size']))
            # print(amount >= float(det['min_size']))
            o = client.place_limit_order(product_id=ticker, size=amount, price=price, side="buy")
            pprint(o)
            msg = {"type": "success", "exchange": "COINBASEPRO", "price": price, "side": "buy", "size": o['size'],
                   "symbol": ticker, 'ordertype': "limit"}
        else:
            o = None
            msg = {"type": "error", "exchange": "COINBASEPRO", "symbol": ticker, "side": "buy",
                   "error": f"You are trying to sell {amount} which is less than minimum allowed {det['base_min_size']}"}
    else:
        o = client.place_market_order(product_id=ticker, funds=usd, side="buy")
        pprint(o)
        msg = {"type": "success", "exchange": "COINBASEPRO", "price": usd, "size": None, "side": "buy",
               "symbol": ticker, 'ordertype': "market"}

    if o is not None:
        pprint(o)
        add_order(o['id'], reset)

    return msg


# This is added so that many files can reuse the function get_database()
if __name__ == "__main__":
    # Get the database
    dbname = get_balance_ticker('ETHUSD')
