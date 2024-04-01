from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting. test import SMA, EURUSD 

class MovingAverageCrossStrategy(Strategy):
    def init(self):
        # Define short-term (fast) and long-term (slow) moving averages
        close = self.data.Close
        self.fast_ma = self.I(SMA, close , 10)  # 20-period fast MA
        self.slow_ma = self.I(SMA, close, 20)  # 50-period slow MA

    def next(self):
        # Buy signal: fast MA crosses above slow MA
        if crossover(self.fast_ma, self.slow_ma):
            self.position.close()
            self.buy()

        # Sell signal: fast MA crosses below slow MA
        elif crossover(self.slow_ma, self.fast_ma):
            self.position.close()
            self.sell()

# Backtest the strategy
import pandas as pd 
data = pd.read_csv ('EURUSDM1.csv',encoding='utf-16')
data.set_index('Time',inplace=True)
bt = Backtest(EURUSD, MovingAverageCrossStrategy, cash=10000, commission=.002)
stats = bt.run()
print(stats)
