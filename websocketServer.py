from threading import Thread

from socketsHandler.coinbase_pro_wh import CoinBaseProWebsocketClient
from socketsHandler.ftx_wh import FtxWebsocketClient
from socketsHandler.gemini_wh import GeminiWebsocketClient


def startFTXServer():
    try:
        ftxwh = FtxWebsocketClient()
        ftxwh.start()
    except Exception as err:
        print(err)
        print("FTX Connect Failed")


def startCoinBaseServer():
    try:
        cwh = CoinBaseProWebsocketClient()
        cwh.start()
    except Exception as err:
        print(err)
        print("CoinBase Connect failed")


def startGeminiServer():
    try:
        gwh = GeminiWebsocketClient()
        gwh.start()
    except Exception as err:
        print(err)
        print("connect failed")


def main():
    t1 = Thread(target=startGeminiServer)
    t2 = Thread(target=startGeminiServer)
    t3 = Thread(target=startCoinBaseServer)

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()
