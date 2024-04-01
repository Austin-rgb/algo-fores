import MetaTrader5 as mt5
import pandas as pd
from time import sleep
from threading import Thread

# Initialize mt5 or exit
if not mt5.initialize():
    print('Could not initialize mt5, please confirm your internet connectivity')
    exit()

# Login
login = 5023224530
password = 'P*ZoK4Sv'
server = 'MetaQuotes-Demo'
if not mt5.login(login, password, server):
    print('Login failed')
    exit()


def r_signal(signal, timeframes: list):
    if len(timeframes) == 1:
        return signal(timeframes[0])
    else:
        signal_a = signal(timeframes[0])
        signal_b = r_signal(signal, timeframes[1:])
        if signal_a == signal_b:
            return signal_a
        else:
            return 'ignore'


def account_info():
    account = mt5.account_info()
    if account is None:
        return None
    else:
        return f'Balance: {account.balance}, Equity: {account.equity}, Free margin: {account.margin_free}'


class Platform:
    def __init__(self):
        # Parameters
        self.symbol = 'EURUSD'
        self.avg_length = 60
        self.fast_avg_length = 15
        self.target_profit = .0002
        self.deviation = 1
        self.lot = .1
        self.commission = .00016
        self.spread = .0016

        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            print(f'{self.symbol} info not found')
            mt5.shutdown()
            exit()

        if not symbol_info.visible:
            print('{symbol} info not visible')
            if not mt5.symbol_select(self.symbol, True):
                print(f'{self.symbol} selection failed')
                mt5.shutdown()
                exit()

    def sell(self):
        price = mt5.symbol_info_tick(self.symbol).bid
        request = {
            'type': mt5.ORDER_TYPE_SELL,
            'price': price,
            'tp': price - self.target_profit,
            'comment': 'python script open',
        }
        return self.send_order(request)

    def buy(self):
        price = mt5.symbol_info_tick(self.symbol).ask
        request = {
            'type': mt5.ORDER_TYPE_BUY,
            'price': price,
            'tp': price + self.target_profit,
            'comment': 'python script open',
        }
        return self.send_order(request)

    def send_order(self, request):
        request['action'] = mt5.TRADE_ACTION_DEAL
        request['symbol'] = self.symbol
        request['volume'] = self.lot
        request['magic'] = 234000
        request['deviation'] = self.deviation
        request['type_filling'] = mt5.ORDER_FILLING_FOK
        request['type_time'] = mt5.ORDER_TIME_GTC
        result = mt5.order_send(request)
        if result is None:
            print('order failed, error code =', mt5.last_error())
            sleep(1)
            return
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f'Order failed, error code: {mt5.last_error()}')
            sleep(1)
        else:
            print(f'Order success')
        return result

    def close_order(self, request, position_id):
        request['position'] = position_id
        del (request['tp'])
        return self.send_order(request)

    def xover_signal(self,timeframe,period1,period2):
        long_period = 0
        short_period = 0
        if period1 > period2:
            long_period = period1
            short_period = period2
        elif period2 > period1:
            long_period = period2
            short_period = period1
        elif period1 > 2:
            long_period = period1 + 1
            short_period = period2 - 1

        else:
            long_period = 30
            short_period = 15
        mt_rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, long_period+1)
        rates = pd.DataFrame(mt_rates)
        opens = rates['open'].values[1:]
        last_opens = rates['open'].values[:-1]
        long_mean = opens.mean()
        short_mean = opens[-short_period:].mean()
        last_long_mean = last_opens.mean()
        last_short_mean = last_opens[-short_period:].mean()
        if last_long_mean > last_short_mean and long_mean<= short_mean:
            return 'buy'
        elif last_long_mean < last_short_mean and long_mean>= short_mean:
            return 'sell'
        else:
            return 'ignore'


    def avg_signal(self, timeframe):
        mt_rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, self.avg_length)
        rates = pd.DataFrame(mt_rates)
        highs = rates['high'].values.mean()
        lows = rates['low'].values.mean()
        fast_avg = rates['open'].values[-15:].mean()
        if fast_avg > highs:
            return 'sell'
        elif fast_avg < lows:
            return 'buy'
        else:
            return 'ignore'

    def acc_signal(self, timeframe):
        mt_rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, self.avg_length)
        rates = pd.DataFrame(mt_rates)
        highs = rates['high'].values.mean()
        lows = rates['low'].values.mean()
        sell_price = mt5.symbol_info_tick(self.symbol).bid
        buy_price = mt5.symbol_info_tick(self.symbol).ask
        if sell_price > highs:
            return 'sell'
        elif buy_price < lows:
            return 'buy'
        else:
            return 'ignore'


class TradeTimer:
    
    """
    A general class for detecting the best time to make an order
    Please subclass it to implement methods; on_approaching and on_reached to implement what to do on_approaching and on_reached
    """

    def __init__(self, platform: Platform, timeframes: list):
        """
        Creates TradeTimer object
        self.timer_thread is created but not started, make sure you start it in your subclass of this class
        :param platform:
        :param timeframes:
        """
        self.timeframes = timeframes
        self.platform = platform
        self.reached = None
        self.approached = None
        self.gone = None
        self.timer_thread = Thread(target=self.timer2)
        self.running = True

    def timer(self):
        while self.running:
            approaching = r_signal(self.platform.acc_signal, [15, 5, 1])
            if approaching != 'ignore':
                self._on_approaching(approaching)
            else:
                self._on_gone(self.approached)
            reached = r_signal(self.platform.avg_signal, [15, 5, 1])
            if reached != 'ignore':
                self._on_reached(reached)
            else:
                self._on_gone(self.reached)
            sleep(1)

    def timer2(self):
        timeframe = 5
        while self.running:
            reached = self.platform.xover_signal(timeframe,15,30)
            if reached != 'ignore':
                self._on_reached(reached)
            else:
                self._on_gone(self.reached)
            sleep(timeframe*60)

    def _on_reached(self, signal):
        if self.reached != signal:
            self.on_reached(signal)
            self.reached = signal

    def _on_approaching(self, signal):
        if self.approached != signal:
            self.on_approaching(signal)
            self.approached = signal

    def _on_gone(self, signal):
        if self.gone != signal:
            self.on_gone(signal)
            self.gone = signal

    def on_approaching(self, signal):
        """
        Called when a trade signal is approaching
        Just prints that the approaching signal
        You can subclass the TradeTimer class to implement this method with what suits your needs
        :param signal:
        :return:
        """
        print(f'{signal} period approaching')

    def on_reached(self, signal):
        """
        Called when a trade signal is reached
        By default it just prints that the signal is reached
        You can subclass the TradeTimer class to implement this method with what suits your needs
        :param signal:
        :return:
        """
        print(f'{signal} period reached')

    def on_gone(self, signal):
        """
        Called when a trade signal is gone
        By default it just prints that the signal is gone
        You can subclass the TradeTimer class to implement this method with what suits your needs
        :param signal:
        :return:
        """
        print(f'{signal} period reached')

    def stop(self):
        """
        Stops the TradeTimer service
        :return:
        """
        self.running = False
        self.timer_thread.join()


class LocalTrader(TradeTimer):
    def __init__(self, platform: Platform, timeframes: list):
        super().__init__(platform, timeframes)

    def on_reached(self, signal):
        if signal == 'buy':
            self.platform.buy()
        elif signal == 'sell':
            self.platform.sell()


import socket


class Messenger:
    def __init__(self):
        # Create a socket object
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Bind the socket to a specific address and port
        server_address = ('', 8888)
        server_socket.bind(server_address)

        # Listen for incoming connections
        server_socket.listen(1)

        print('Server is waiting for connections...')

        # Wait for a connection
        client_socket, client_address = server_socket.accept()
        self.socket = client_socket
        print('Connection from', client_address)

    def send(self, msg):
        self.socket.sendall(bytes(msg, 'utf-8'))


class RemoteTrader(TradeTimer):
    """
    Send trade signals to remote clients through sockets
    """

    def __init__(self, platform: Platform, timeframes: list):
        """
        Creates a RemoteTrade object for sending trade signals to clients
        It uses sockets to communicate with clients
        It starts a messaging server which needs at least one client connected to start the service
        Therefore ensure you connect at least one client to continue
        Use address = ('<your-ip>',8888)
        :param platform:
        :param timeframes:
        """
        super().__init__(platform, timeframes)
        self.messenger = Messenger()
        self.timer_thread.start()

    def on_reached(self, signal):
        self.messenger.send(f'{signal} period reached')

    def on_approaching(self, signal):
        self.messenger.send(f'{signal} period approaching')


plat = Platform()
frames = [15, 5, 1]

trader = RemoteTrader(plat, frames)
