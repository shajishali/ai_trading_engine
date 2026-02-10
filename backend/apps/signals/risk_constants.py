"""
Mandatory risk parameters for leveraged trading.

When leverage is 10x:
- Take profit: 50% of capital (mandatory)
- Stop loss: 25% of capital (mandatory)

At 10x leverage, capital P&L = price_move_pct * leverage.
So: 50% capital profit = 5% price move, 25% capital loss = 2.5% price move.
"""

# Leverage used for futures/margin trading
LEVERAGE_10X = 10

# Mandatory capital-based targets when using 10x leverage
TAKE_PROFIT_CAPITAL_PERCENT = 50.0   # 50% profit of capital
STOP_LOSS_CAPITAL_PERCENT = 25.0     # 25% max loss of capital

# Derived price move percentages: capital_pct / leverage
TAKE_PROFIT_PRICE_PERCENT_10X = TAKE_PROFIT_CAPITAL_PERCENT / LEVERAGE_10X   # 5%
STOP_LOSS_PRICE_PERCENT_10X = STOP_LOSS_CAPITAL_PERCENT / LEVERAGE_10X       # 2.5%

# As decimals for calculations (e.g. entry * (1 + x))
TAKE_PROFIT_PRICE_DECIMAL_10X = TAKE_PROFIT_PRICE_PERCENT_10X / 100.0   # 0.05
STOP_LOSS_PRICE_DECIMAL_10X = STOP_LOSS_PRICE_PERCENT_10X / 100.0       # 0.025
