from pprint import pprint

import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption
from pymongo import MongoClient
from exchanges import gemini_bot, ftx_bot, coinbase_pro_bot
from utils import notification

from dotenv import dotenv_values

config = dotenv_values(".env")

dbclient = MongoClient(config['MONGODB_URL'])
db = dbclient['tradingbot']


class Confirm(nextcord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @nextcord.ui.button(label='Confirm', style=nextcord.ButtonStyle.green)
    async def confirm(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message('Confirming', ephemeral=True)
        self.value = True
        self.stop()

    @nextcord.ui.button(label='Cancel', style=nextcord.ButtonStyle.grey)
    async def cancel(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message('Cancelling', ephemeral=True)
        self.value = False
        self.stop()


intents = nextcord.Intents.default()

client = commands.Bot(command_prefix='!', intents=intents, description="Trading bot")


@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')


# DISCORD_GUILD_ID = 865695105406599188
# ,guild_ids=[config.DISCORD_GUILD_ID]

@client.slash_command(name="buy", description="This is place a buy order.")
async def buy(
        interaction: Interaction,
        ticker: str = SlashOption(name="ticker", required=True),
        amount: str = SlashOption(name="amount", required=True),
        price: str = SlashOption(name="price", required=True),
        exchanges: str = SlashOption(name="exchanges", required=True),
        reset: str = SlashOption(name="resetorder", choices=['True', 'False'], default='False', required=True)
):
    ticker = (ticker + 'usd').upper()

    exchanges = exchanges.split(',')
    exchanges = [int(i) for i in exchanges]

    if reset == 'False':
        reset = False
    else:
        reset = True

    price = float(price)

    # print(price)
    # print(ticker)
    # print(exchanges)
    # print(reset)

    embeds = []

    for i in exchanges:
        if i == 1:
            exchange_name = "Gemini US"
        elif i == 2:
            exchange_name = "FTX US"
        else:
            exchange_name = "CoinBasePro"

        dic = nextcord.Embed(
            description=f"Do you want to place a buy order of {amount} on {exchange_name} at {price} with reset as {str(reset)}?")
        embeds.append(dic)

    view = Confirm()

    await interaction.response.send_message(f'Buy Order confirmation for {ticker}', embeds=embeds, view=view)

    await view.wait()
    if view.value is None:
        print('Timed out...')
        await interaction.response.send_message('Timed out')
    elif view.value:
        print('Confirmed...')

        results = []

        for i in exchanges:

            if i == 1:
                if gemini_bot.check_ticker_by_nickname(ticker):
                    t = gemini_bot.get_ticker_info_by_nickname(ticker)
                    new_amount = amount
                    if new_amount[0] == '$':
                        new_amount = float(new_amount[1:])
                    else:
                        new_amount = new_amount[:-1]
                        usd = gemini_bot.get_usd_balance()
                        new_amount = (new_amount * usd) / 100.0

                    print(new_amount)
                    msgs = gemini_bot.buy(t['ticker'], usd=new_amount, price=price, ordertype="limit")
                    results.append(msgs)
                else:
                    msg = {"type": "error", "exchange": "GEMINI", "symbol": ticker, "side": "buy",
                           "error": f"No symbol available for {ticker}"}
                    results.append(msg)

            elif i == 2:
                if ftx_bot.check_ticker_by_nickname(ticker):
                    t = ftx_bot.get_ticker_info_by_nickname(ticker)
                    new_amount = amount

                    if new_amount[0] == '$':
                        new_amount = float(new_amount[1:])
                    else:
                        new_amount = new_amount[:-1]
                        usd = ftx_bot.get_usd_balance()
                        new_amount = new_amount * usd

                    if 1 in exchanges:
                        new_amount = 0.2 * new_amount

                    msgs = ftx_bot.buy(t['ticker'], usd=new_amount, price=price, ordertype="limit")
                    results.append(msgs)
                else:
                    msg = {"type": "error", "exchange": "FTXUS", "symbol": ticker, "side": "buy",
                           "error": f"No symbol available for {ticker}"}
                    results.append(msg)

            elif i == 3:
                if coinbase_pro_bot.check_ticker_by_nickname(ticker):
                    t = coinbase_pro_bot.get_ticker_info_by_nickname(ticker)

                    new_amount = amount

                    if new_amount[0] == '$':
                        new_amount = float(new_amount[1:])
                    else:
                        new_amount = new_amount[:-1]
                        usd = coinbase_pro_bot.get_usd_balance()
                        new_amount = new_amount * usd

                    if 1 in exchanges:
                        new_amount = 0.2 * new_amount

                    msgs = coinbase_pro_bot.buy(t['ticker'], usd=new_amount, price=price, ordertype="limit")
                    results.append(msgs)
                else:
                    msg = {"type": "error", "exchange": "COINBASEPRO", "symbol": ticker, "side": "buy",
                           "error": f"No symbol available for {ticker}"}
                    results.append(msg)

        notification.buy_notification(results)

    else:
        print('Cancelled...')


# { nickname_ticker : "BTCUSD", // name which we will get from trading view
#   ticker : "BTCUSD", // realname which is used in the platform
#   avg_price : 123.21,
#   amount_per : 1,2,3,4,5,6 ,
#   profit_per : 5,10,15,20,25,30 ,
#   quan : 120}

@client.slash_command(name="add", description="Add a new coin")
async def add(interaction: Interaction,
              ticker: str = SlashOption(name="ticker", required=True),
              exchanges: str = SlashOption(name="exchanges", required=True),
              amount_per: str = SlashOption(name="amount_per", required=True),
              profit_per: str = SlashOption(name="profit_per", required=True),
              nickname: str = SlashOption(name="nickname", required=True),
              ):
    ticker = ticker.upper()
    nickname = nickname.upper()
    exchanges = exchanges.split(',')
    exchanges = [int(i) for i in exchanges]

    for i in exchanges:

        if i == 1:
            tickers_db = db["gemini_tickers"]
        elif i == 2:
            tickers_db = db["ftx_tickers"]
        else:
            tickers_db = db["cbp_tickers"]

        tickers_db.insert_one(
            {"ticker": ticker, "nickname": nickname, "avg_price": 0, "quan": 0, "profit_per": profit_per,
             "amount_per": amount_per})

    await interaction.send(f"{ticker} has been successfully added to the trading bot.")


client.run(config['DISCORD_TOKEN'])
