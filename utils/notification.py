import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pprint import pprint
from socket import gaierror
from typing import Dict

import pandas as pd
import requests

from dotenv import dotenv_values
config = dotenv_values(".env")


def discord(message):
    try:
        req = requests.post(config['DISCORD_WEBHOOK'], data=json.dumps(message),
                            headers={"Content-Type": "application/json"})
        req.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(err)
        print(message)


def sendmail(subject, html):
    message = MIMEMultipart("alternative")

    message["From"] = config['FROM_EMAIL']
    message["To"] = config['TO_EMAIL']

    message["Subject"] = subject

    body = MIMEText(html, "html")
    message.attach(body)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(config['FROM_EMAIL'], config['FROM_EMAIL_PASSWORD'])
            server.sendmail(config['FROM_EMAIL'], config['TO_EMAIL'], message.as_string())

            print(f'mail sent to {config["TO_EMAIL"]} ')

    except (gaierror, ConnectionRefusedError):
        print('Failed to connect to the server. Bad connection settings?')
    except smtplib.SMTPServerDisconnected:
        print('Failed to connect to the server. Wrong user/password?')
    except smtplib.SMTPException as e:
        print('SMTP error occurred: ' + str(e))


# msg = {"type": "success", "exchange": "GEMINI", "price": last_price, "size": o['original_amount'],
# "symbol": ticker, 'ordertype': "market"}
# msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker,
# "error": f"You are trying to buy {amount} which is less than minimum allowed {det['min_order_size']}"}

def discord_buy_sell(msgs):
    all_embeds = []

    for i in msgs:
        if i['type'] == "success":
            if i['side'] == "buy":
                title = "New buy order created"
                subject = f"New Buy order created for {i['symbol']}, {i['exchange']}"
            else:
                title = "New sell order created"
                subject = f"New Sell order created for {i['symbol']}, {i['exchange']}"

            message = {
                "title": title,
                "color": 15251703,
                "fields": [
                    {
                        "name": "Exchange",
                        "value": str(i['exchange']),
                        "inline": True
                    },
                    {
                        "name": "Symbol",
                        "value": str(i['symbol']),
                        "inline": True
                    },
                    {
                        "name": "Price",
                        "value": str(i['price']),
                        "inline": True
                    },
                    {
                        "name": "Size",
                        "value": str(i['size']),
                        "inline": True
                    },
                    {
                        "name": "Order Type",
                        "value": str(i['ordertype']),
                        "inline": True
                    }
                ],
            }

            all_embeds.append(message)

            html = """\
                    <html>
                      <head>
                      </head>
                      <body>
                        New buy order for {0} has been created in {1}.
                        <br />
                        Size - {2}
                        <br />
                        Price - {3}
                        <br />
                        Order Type - {4}
                      </body>
                    </html>
                    """.format(i['symbol'], i['exchange'], i['size'], i['price'], i['ordertype'])

            sendmail(subject, html)

        else:
            if i['side'] == "buy":
                title = "Error while creating buy order"
                subject = f"Error while creating buy order for {i['symbol']}, {i['exchange']}"
            else:
                title = "Error while creating sell order"
                subject = f"Error while creating sell order for {i['symbol']}, {i['exchange']}"

            message = {
                "title": title,
                "color": 15251703,
                "fields": [
                    {
                        "name": "Exchange",
                        "value": str(i['exchange']),
                        "inline": True
                    },
                    {
                        "name": "Symbol",
                        "value": str(i['symbol']),
                        "inline": True
                    },
                    {
                        "name": "Reason",
                        "value": str(i['error'])
                    },
                ],
            }

            all_embeds.append(message)

            html = """\
                <html>
                  <head>
                  </head>
                  <body>
                   Error - {0}
                  </body>
                </html>
                """.format(i['error'])

            sendmail(subject, html)

    dm = {
        "username": "Trading bot alerts",
        "embeds": all_embeds
    }

    discord(dm)


def buy_notification(msgs):
    pprint(msgs)
    discord_buy_sell(msgs)


def sell_notification(msgs):
    pprint(msgs)
    discord_buy_sell(msgs)


def reset_single_notification(msg):
    pprint(msg)
    all_embeds = []

    if isinstance(msg['data'], Dict) and msg['data']['type'] == "error":
        message = {
            "title": "Error while resetting sell orders",
            "color": 15251703,
            "fields": [
                {
                    "name": "Reason",
                    "value": str(msg['data']['error'])
                }
            ],
        }

        all_embeds.append(message)
    else:
        for i in msg['data']:
            message = {
                "title": "Limit sell order created",
                "color": 15251703,
                "fields": [
                    {
                        "name": "Price",
                        "value": str(i['price']),
                        "inline": True
                    },
                    {
                        "name": "Size",
                        "value": str(i['size']),
                        "inline": True
                    }
                ],
            }

            all_embeds.append(message)

    dm = {
        "username": "Trading bot alerts",
        "content": f"This is for {str(msg['exchange'])} - {str(msg['symbol'])}",
        "embeds": all_embeds
    }

    discord(dm)

    subject = f"Reset orders created - {str(msg['exchange'])} - {str(msg['symbol'])}"

    if isinstance(msg['data'], Dict):
        x = f"Error - {str(msg['data']['error'])}"
    else:
        s = []
        for x in msg['data']:
            s.append({"price": x['price'], "size": x['size']})

        tab = pd.DataFrame(s, columns=["size", "price"])
        x = tab.to_html()

    html = """\
        <html>
          <head>
          <style> 

              table {{
                  color:black;
                  border-collapse: collapse;
                  width: 100%;
                }}

                th, td {{
                  text-align: left;
                  padding: 8px;
                }}

                tr:nth-child(even){{background-color: #f2f2f2}}

                th {{
                  background-color: #04AA6D;
                  color: white;
                }}
        </style>
          </head>
          <body>
            Limit sells order for {0} has been created.
            <br />
            {1}
            <br />
          </body>
        </html>
        """.format({str(msg['symbol'])}, x)

    sendmail(subject, html)


def reset_notification(msgs):
    for i in msgs:
        reset_single_notification(i)


# msg = {"type": "success", "exchange": "COINBASEPRO", "symbol": ticker, "side": "buy",
# "price": price, "size": size, "usd": price * size, "avgbuyprice": avgbuyprice}
def buy_filled(msg):
    pprint(msg)

    dm = {
        "username": "Trading bot alerts",
        "content": f"This is for {str(msg['exchange'])} - {str(msg['symbol'])}",
        "embeds": [
            {
                "title": "Buy Order Filled",
                "color": 15251703,
                "fields": [
                    {
                        "name": "Price",
                        "value": str(msg['price']),
                        "inline": True
                    },
                    {
                        "name": "Size",
                        "value": str(msg['size']),
                        "inline": True
                    },
                    {
                        "name": "Amount in USD",
                        "value": str(msg['usd']),
                        "inline": True
                    },
                    {
                        "name": "Current Avg Buy Price",
                        "value": str(msg['avgbuyprice']),
                        "inline": True
                    }
                ],
            }
        ]
    }

    discord(dm)

    subject = f"Buy Order filled - {msg['symbol']}, {msg['exchange']}"
    html = """\
        <html>
          <head>
          </head>
          <body>
            New buy order for {0} has been filled in {1}.
            <br />
            Size - {2}
            <br />
            Price - {3}
            <br />
            Amount in USD - {4}
            <br />
            Average buy price - {5}
          </body>
        </html>
        """.format(msg['symbol'], msg['exchange'], msg['size'], msg['price'], msg['usd'], msg['avgbuyprice'])

    sendmail(subject, html)


# msg = {"type": "success", "exchange": "COINBASEPRO", "symbol": ticker, "side": "sell",
# "size": size, "usd": order_info['funds'], "avgbuyprice": inf['avg_price']}
def sell_filled(msg):
    pprint(msg)

    dm = {
        "username": "Trading bot alerts",
        "content": f"This is for {str(msg['exchange'])} - {str(msg['symbol'])}",
        "embeds": [
            {
                "title": "Sell Order Filled",
                "color": 15251703,
                "fields": [
                    {
                        "name": "Size",
                        "value": str(msg['size']),
                        "inline": True
                    },
                    {
                        "name": "Amount in USD",
                        "value": str(msg['usd']),
                        "inline": True
                    },
                    {
                        "name": "Current Avg Buy Price",
                        "value": str(msg['avgbuyprice']),
                        "inline": True
                    }
                ],
            }
        ]
    }

    discord(dm)

    subject = f"Limit Sell Order filled - {msg['symbol']}, {msg['exchange']}"
    html = """\
            <html>
              <head>
              </head>
              <body>
                Limit sell order for {0} has been filled.
                <br />
                Size - {1}
                <br />
                Amount in USD - {2}
                <br />
                Average buy price - {3}
              </body>
            </html>
            """.format(msg['symbol'], msg['size'], msg['usd'], msg['avgbuyprice'])

    sendmail(subject, html)


def cancelled_success(msgs):
    results = []

    for i in msgs:
        if i['type'] == "success":
            t = {
                "title": "Cancel Order success",
                "color": 15251703,
                "fields": [
                    {
                        "name": "Exchange",
                        "value": str(i['exchange']),
                        "inline": True
                    },
                    {
                        "name": "Symbol",
                        "value": str(i['symbol']),
                        "inline": True
                    },
                    {
                        "name": "Message",
                        "value": str(i['success'])
                    },
                ],
            }

            results.append(t)
        else:
            t = {
                "title": "Cancel Order Error",
                "color": 15251703,
                "fields": [
                    {
                        "name": "Exchange",
                        "value": str(i['exchange']),
                        "inline": True
                    },
                    {
                        "name": "Symbol",
                        "value": str(i['symbol']),
                        "inline": True
                    },
                    {
                        "name": "Reason",
                        "value": str(i['error'])
                    },
                ],
            }

            results.append(t)

    dm = {
        "username": "Trading bot alerts",
        "embeds": results
    }

    discord(dm)
