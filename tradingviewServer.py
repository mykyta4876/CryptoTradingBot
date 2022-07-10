import json
from pprint import pprint

from flask import Flask, jsonify, request

from dotenv import dotenv_values

config = dotenv_values(".env")

from utils import notification

from exchanges import ftx_bot, coinbase_pro_bot, gemini_bot

app = Flask(__name__)


@app.route("/", methods=['GET'])
def mainpage():
    return jsonify({'message': "Server is working properly. \n Made by Harsh agarwal"})


@app.route("/tv_webhook", methods=['POST'])
def tvwebhook():
    data = json.loads(request.data)
    # data = request.data

    pprint(data)

    if "passphrase" not in data or "ticker" not in data or "price" not in data:
        return jsonify(
            {
                "code": "error",
                "message": "invalid format"
            }
        )

    if data["passphrase"] != config['WEBHOOK_PASSPHRASE']:
        return jsonify(
            {
                "code": "error",
                "message": "invalid passphrase"
            }
        )

    ticker = data['ticker'].strip()
    price = data['price'].strip()

    if "exchangeOrder" not in data:
        exchanges = [1]
    else:
        exchanges = data['exchangeOrder'].split(',')
        exchanges = [int(i) for i in exchanges]

    if "cancelOpenOrder" in data:
        if data["cancelOpenOrder"] == 'Y':

            pprint("running cancelorders ")

            results = []

            for i in exchanges:
                if i == 1:
                    if gemini_bot.check_ticker_by_nickname(ticker):
                        t = gemini_bot.get_ticker_info_by_nickname(ticker)
                        msgs = gemini_bot.cancel_orders(t['ticker'])
                        results.append(msgs)
                elif i == 2:
                    if ftx_bot.check_ticker_by_nickname(ticker):
                        t = ftx_bot.get_ticker_info_by_nickname(ticker)
                        msgs = ftx_bot.cancel_orders(t['ticker'])
                        results.append(msgs)
                elif i == 3:
                    if coinbase_pro_bot.check_ticker_by_nickname(ticker):
                        t = coinbase_pro_bot.get_ticker_info_by_nickname(ticker)
                        msgs = coinbase_pro_bot.cancel_orders(t['ticker'])
                        results.append(msgs)

            notification.cancelled_success(results)

            return jsonify(
                {
                    "code": "success",
                    "message": "cancelled orders command run successfully",
                    "data": results
                }
            )

    if "orderType" not in data:
        ordertype = "limit"
    else:
        ordertype = data['orderType']

    if "resetOrder" not in data:
        resetorder = False
    else:
        resetorder = data["resetOrder"] == 'Y'

    if "direction" not in data:
        direction = "buy"
    else:
        direction = "sell"

    if direction == "sell":
        if "sellPercent" not in data:
            sellpercent = 0
        else:
            sellpercent = float(data['sellPercent'])

        if 0 < sellpercent <= 100:

            pprint("running sellpercent")

            sellpercent = float(sellpercent / 100.00)

            results = []
            for i in exchanges:

                if i == 1:
                    if gemini_bot.check_ticker_by_nickname(ticker):
                        t = gemini_bot.get_ticker_info_by_nickname(ticker)
                        bal = float(gemini_bot.get_balance_ticker(t['ticker']))

                        print(sellpercent * bal)

                        msgs = gemini_bot.sell(t['ticker'], amount=sellpercent * bal, price=price, reset=resetorder)
                        results.append(msgs)
                    else:
                        msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker, "side": "sell",
                               "error": f"No symbol available for {ticker}"}
                        results.append(msg)

                elif i == 2:
                    if ftx_bot.check_ticker_by_nickname(ticker):
                        t = ftx_bot.get_ticker_info_by_nickname(ticker)
                        bal = float(ftx_bot.get_balance_ticker(t['ticker']))
                        if 1 in exchanges:
                            sellpercent = 0.2 * sellpercent

                        print(sellpercent * bal)

                        msgs = ftx_bot.sell(t['ticker'], amount=sellpercent * bal, price=price, reset=resetorder)
                        results.append(msgs)
                    else:
                        msg = {"type": "error", "exchange": "FTXUS", "symbol": ticker, "side": "sell",
                               "error": f"No symbol available for {ticker}"}
                        results.append(msg)

                elif i == 3:
                    if coinbase_pro_bot.check_ticker_by_nickname(ticker):
                        t = coinbase_pro_bot.get_ticker_info_by_nickname(ticker)
                        bal = float(coinbase_pro_bot.get_balance_ticker(t['ticker']))
                        if 1 in exchanges:
                            sellpercent = 0.1 * sellpercent

                        print(sellpercent * bal)

                        msgs = coinbase_pro_bot.sell(t['ticker'], amount=sellpercent * bal, price=price,
                                                     reset=resetorder)
                        results.append(msgs)
                    else:
                        msg = {"type": "error", "exchange": "COINBASEPRO", "symbol": ticker, "side": "sell",
                               "error": f"No symbol available for {ticker}"}
                        results.append(msg)

            notification.sell_notification(results)

            return jsonify(
                {
                    "code": "success",
                    "message": "sell orders placed successfully",
                    "data": results
                }
            )

        else:

            return jsonify(
                {
                    "code": "error",
                    "message": "sell percent not in range of 0 to 100"
                }
            )

    if resetorder:

        pprint("running resetorders")

        results = []
        for i in exchanges:

            if i == 1:

                if gemini_bot.check_ticker_by_nickname(ticker):
                    t = gemini_bot.get_ticker_info_by_nickname(ticker)
                    msgs = gemini_bot.reset_orders(t['ticker'])
                else:
                    msgs = {"type": "error", "exchange": "GEMINI", "symbol": ticker,
                            "error": f"No symbol available for {ticker}"}

                t = {"exchange": "GEMINI", "symbol": ticker, "data": msgs}
                results.append(t)

            elif i == 2:

                if ftx_bot.check_ticker_by_nickname(ticker):
                    t = ftx_bot.get_ticker_info_by_nickname(ticker)
                    msgs = ftx_bot.reset_orders(t['ticker'])
                else:
                    msgs = {"type": "error", "exchange": "FTXUS", "symbol": ticker,
                            "error": f"No symbol available for {ticker}"}

                t = {"exchange": "FTXUS", "symbol": ticker, "data": msgs}
                results.append(t)

            elif i == 3:
                if coinbase_pro_bot.check_ticker_by_nickname(ticker):
                    t = coinbase_pro_bot.get_ticker_info_by_nickname(ticker)
                    msgs = coinbase_pro_bot.reset_orders(t['ticker'])
                else:
                    msgs = {"type": "error", "exchange": "COINBASEPRO", "symbol": ticker,
                            "error": f"No symbol available for {ticker}"}

                t = {"exchange": "COINBASEPRO", "symbol": ticker, "data": msgs}
                results.append(t)

        notification.reset_notification(results)

        return jsonify(
            {
                "code": "success",
                "message": "reset orders successfully",
                "data": results
            }
        )

    if "amount" not in data:
        amount = 0
    else:
        amount = float(data["amount"])

    if direction == "buy":

        print("running buy orders")

        results = []
        for i in exchanges:

            if i == 1:
                if gemini_bot.check_ticker_by_nickname(ticker):
                    t = gemini_bot.get_ticker_info_by_nickname(ticker)
                    msgs = gemini_bot.buy(t['ticker'], usd=amount, price=price, ordertype=ordertype)
                    results.append(msgs)
                else:
                    msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker, "side": "buy",
                           "error": f"No symbol available for {ticker}"}
                    results.append(msg)

            elif i == 2:
                if ftx_bot.check_ticker_by_nickname(ticker):
                    t = ftx_bot.get_ticker_info_by_nickname(ticker)
                    new_amount = amount
                    if 1 in exchanges:
                        new_amount = 0.2 * amount
                    msgs = ftx_bot.buy(t['ticker'], usd=new_amount, price=price, ordertype=ordertype)
                    results.append(msgs)
                else:
                    msg = {"type": "error", "exchange": "FTXUS", "symbol": ticker, "side": "buy",
                           "error": f"No symbol available for {ticker}"}
                    results.append(msg)

            elif i == 3:
                if coinbase_pro_bot.check_ticker_by_nickname(ticker):
                    t = coinbase_pro_bot.get_ticker_info_by_nickname(ticker)
                    new_amount = amount
                    if 1 in exchanges:
                        new_amount = 0.1 * amount
                    msgs = coinbase_pro_bot.buy(t['ticker'], usd=new_amount, price=price, ordertype=ordertype)
                    results.append(msgs)
                else:
                    msg = {"type": "error", "exchange": "COINBASEPRO", "symbol": ticker, "side": "buy",
                           "error": f"No symbol available for {ticker}"}
                    results.append(msg)

        notification.buy_notification(results)

        return jsonify(
            {
                "code": "success",
                "message": "buy orders successfully",
                "data": results
            }
        )


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=443)
