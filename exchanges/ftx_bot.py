from pprint import pprint

from pymongo import MongoClient

import utils.PersonalCopiedFTXClient as ftx

from dotenv import dotenv_values

config = dotenv_values(".env")

client = ftx.FtxClient(api_key=config['FTX_API_KEY'], api_secret=config['FTX_API_SECRET'],
                       subaccount_name=config['FTX_SUBACCOUNT_NAME'])

dbclient = MongoClient(config['MONGODB_URL'])
db = dbclient['tradingbot']
tickers_db = db["ftx_tickers"]
orders_db = db['ftx_orders']


# get balance of particular ticker
def get_balance_ticker(ticker):
    tf = ticker.replace('/USD', '')
    balances = client.get_balances()
    curr_amount = 0
    for b in balances:
        if b['coin'] == tf:
            curr_amount += float(b['availableWithoutBorrow'])

    return float(curr_amount)


# { nickname_ticker : "BTCUSD", // name which we will get from trading view
#   ticker : "BTCUSD", // realname which is used in the platform
#   avg_buyprice : 123.21,
#   amount_per : 1,2,3,4,5,6 ,
#   profit_per : 5,10,15,20,25,30
#   }

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


def check_order(orderid):
    o = orders_db.find_one({"order_id": orderid})

    if o is not None:
        return True
    else:
        return False


def delete_order(orderid):
    orders_db.delete_one({"order_id": str(orderid)})


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
    acc = client.get_balances()
    cur_amount = 0
    for a in acc:
        if a['coin'] == 'USD':
            cur_amount = float(a['availableWithoutBorrow'])

    return cur_amount


def get_symbol_details(ticker):
    t = client.get_market(ticker)
    return t


# cancel open order of particular ticker
def cancel_orders(ticker):
    all_orders = client.get_open_orders()
    cp = 0
    for o in all_orders:
        if o['market'] == ticker:
            cp = 1
            break

    if cp > 0:
        t = client.cancel_orders(market_name=ticker)
        msg = {"type": "success", "exchange": "FTXUS", "symbol": ticker,
               "success": f"All Open orders are successfully cancelled. "}

        return msg
    else:
        msg = {"type": "error", "exchange": "FTXUS", "symbol": ticker,
               "error": f"There are no open orders to cancel."}

        return msg


def check_sell_order(ticker):
    all_orders = client.get_open_orders()
    for o in all_orders:
        if o['market'] == ticker and o['side'] == 'sell':
            return True

    return False


# reset particular ticker
def reset_orders(ticker):
    all_orders = client.get_open_orders()

    for o in all_orders:
        if o['market'] == ticker and o['side'] == 'sell':
            client.cancel_order(o['id'])

    amount = get_balance_ticker(ticker)

    print("resetting amount - ", amount)

    if amount > 0:
        ticker_in = client.get_market(ticker)
        new_price = ticker_in['last']

        ticker_info = get_ticker_info(ticker)
        avg_buy_price = float(ticker_info['avg_price'])

        if avg_buy_price > new_price:
            new_price = avg_buy_price

        new_price = float(new_price)

        return sell_pattern(ticker, amount, new_price)

    else:
        msg = {"type": "error", "exchange": "FTXUS", "symbol": ticker,
               "error": f"There are no existing position to reset."}

        return msg


def sell_pattern(ticker, amount, price):
    price = float(price)
    amount = float(amount)

    ticker_info = get_ticker_info(ticker)

    amount_per = ticker_info['amount_per'].split(',')
    profit_per = ticker_info['profit_per'].split(',')

    pprint(amount_per)
    pprint(profit_per)

    orders = []

    det = get_symbol_details(ticker)
    price_pre = get_precision(det['priceIncrement'])
    amount_pre = get_precision(det['sizeIncrement'])

    msgs = []

    for i in range(0, len(amount_per)):
        new_amount = (float(amount_per[i]) / 100) * amount
        new_amount = round(new_amount, amount_pre)

        new_price = (100 + float(profit_per[i])) * (price / 100.00)
        new_price = round(new_price, price_pre)

        if new_amount >= float(det['minProvideSize']):
            o = client.place_order(market=ticker, size=new_amount,
                                   price=new_price,
                                   side="sell")

            msg = {"type": "success", "exchange": "FTXUS", "price": o['price'], "size": o['size'],
                   "symbol": o['market'],
                   'ordertype': o['type']}

            msgs.append(msg)

            amount = amount - new_amount
            orders.append(o)
        else:
            break

    pprint(orders)

    return msgs


# sell particular ticker
def sell(ticker, amount, price, reset=True):
    price = float(price)
    amount = float(amount)

    det = get_symbol_details(ticker)
    price_pre = get_precision(det['priceIncrement'])
    amount_pre = get_precision(det['sizeIncrement'])

    amount = round(amount, amount_pre)
    price = round(price, price_pre)

    if amount >= float(det['minProvideSize']):
        o = client.place_order(market=ticker, size=amount, price=price, type="limit", side="sell")
        pprint(o)
        msg = {"type": "success", "exchange": "FTXUS", "price": o['price'], "size": o['size'], "symbol": o['market'],
               'ordertype': o['type'], "side": "sell"}

        add_order(o['id'], reset)

    else:
        msg = {"type": "error", "exchange": "FTXUS", "symbol": ticker, "side": "sell",
               "error": f"You are trying to sell {amount} which is less than minimum allowed {det['minProvideSize']}"}

    return msg


def buy(ticker, usd, price=1, ordertype="limit", reset=True):
    price = float(price)
    usd = float(usd)

    det = get_symbol_details(ticker)
    price_pre = get_precision(det['priceIncrement'])
    amount_pre = get_precision(det['sizeIncrement'])

    baln = get_usd_balance()

    if usd > baln:
        msg = {"type": "error", "exchange": "FTXUS", "symbol": ticker, "side": "buy",
               "error": f"You have balance of {baln} but you are trying to buy for {usd}"}

        return msg

    if ordertype == "limit":
        amount = float(usd / price)
        amount = round(amount, amount_pre)
        price = round(price, price_pre)

        if amount >= float(det['minProvideSize']):
            o = client.place_order(market=ticker, size=amount, price=price, side="buy")
            msg = {"type": "success", "exchange": "FTXUS", "price": o['price'], "size": o['size'], "side": "buy",
                   "symbol": o['market'],
                   'ordertype': o['type']}
        else:
            o = None
            msg = {"type": "error", "exchange": "FTXUS", "symbol": ticker, "side": "buy",
                   "error": f"You are trying to buy {amount} which is less than minimum allowed {det['minProvideSize']}"}
    else:
        ticker_in = client.get_market(ticker)
        price = float(ticker_in['last'])
        amount = float(usd / price)

        amount = round(amount, amount_pre)

        if amount >= float(det['minProvideSize']):
            o = client.place_order(market=ticker, price=1, size=amount, side="buy", type="market", ioc=False)
            msg = {"type": "success", "exchange": "FTXUS", "price": price, "size": o['size'], "side": "buy",
                   "symbol": o['market'],
                   'ordertype': o['type']}
        else:
            o = None
            msg = {"type": "error", "exchange": "FTXUS", "symbol": ticker, "side": "buy",
                   "error": f"You are trying to buy {amount} which is less than minimum allowed {det['minProvideSize']}"}

    if o is not None:
        pprint(o)
        add_order(o['id'], reset)

    return msg
