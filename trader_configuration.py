import logging
import numpy as np
import technical_indicators as TI

# Minimum price rounding.
pRounding = 8


def technical_indicators(candles):
    time_values = [candle[0] for candle in candles]
    open_prices = [candle[1] for candle in candles]
    high_prices = [candle[2] for candle in candles]
    low_prices = [candle[3] for candle in candles]
    close_prices = [candle[4] for candle in candles]
    indicators = {
        # 'macd': TI.get_MACD(close_prices, time_values=time_values, map_time=True),
        'RSI': TI.get_RSI(close_prices, time_values=time_values, map_time=True),
        'BB': TI.get_BOLL(close_prices, time_values=time_values, map_time=True),
        'ema': {
            'ema200': TI.get_EMA(close_prices, 200, time_values=time_values, map_time=True)
        }
    }
    return indicators


def search_price(candles):
    high_prices = [candle[2] for candle in candles]
    low_prices = [candle[3] for candle in candles]
    low_price = min(low_prices)
    high_price = max(high_prices)
    return low_price, high_price


'''
--- Current Supported Order ---
    Below are the currently supported order types that can be placed which the trader

-- MARKET --
    To place a MARKET order you must pass:
        'side'              : 'SELL', 
        'description'       : 'Long exit signal', 
        'order_type'        : 'MARKET'
    
-- LIMIT STOP LOSS --
    To place a LIMIT STOP LOSS order you must pass:
        'side'              : 'SELL', 
        'price'             : price,
        'stopPrice'         : stopPrice,
        'description'       : 'Long exit stop-loss', 
        'order_type'        : 'STOP_LOSS_LIMIT'

-- LIMIT --
    To place a LIMIT order you must pass:
        'side'              : 'SELL', 
        'price'             : price,
        'description'       : 'Long exit stop-loss', 
        'order_type'        : 'LIMIT'

-- OCO LIMIT --
    To place a OCO LIMIT order you must pass:
        'side'              : 'SELL', 
        'price'             : price,
        'stopPrice'         : stopPrice,
        'stopLimitPrice'    : stopLimitPrice,
        'description'       : 'Long exit stop-loss', 
        'order_type'        : 'OCO_LIMIT'

--- Key Descriptions--- 
    Section will give brief descript of what each order placement key is and how its used.
        side            = The side the order is to be placed either buy or sell.
        price           = Price for the order to be placed.
        stopPrice       = Stop price to trigger limits.
        stopLimitPrice  = Used for OCO to to determine price placement for part 2 of the order.
        description     = A description for the order that can be used to identify multiple conditions.
        order_type      = The type of the order that is to be placed.

--- Candle Structure ---
    Candles are structured in a multidimensional list as follows:
        [[time, open, high, low, close, volume], ...]
'''


def long_exit_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    # Place Long exit (sell) conditions under this section.
    trade_information['side'] = 'SELL'
    trade_information['price'] = trade_information['price'] * 1.236
    trade_information['description'] = 'SELL LIMIT signal'
    trade_information['order_type'] = 'LIMIT'
    return trade_information


def long_entry_conditions(trade_information, indicators, prices, candles, symbol):
    # Place Long entry (buy) conditions under this section.
    RSI = indicators['RSI']
    BB = indicators['BB']
    low, high = search_price(candles)
    # trade_information['can_order'] = False
    # if RSI[1] < 30 and candles[1][4] > candles[1][3] and BB[1]['B'] > candles[1][3]:
    #     trade_information['side'] = 'BUY'
    #     trade_information['price'] = candles[1][3]
    #     trade_information['description'] = 'Long entry signal'
    #     trade_information['type'] = 'LIMIT'
    #     trade_information['can_order'] = True
    #     return trade_information
    # return None
    trade_information['side'] = 'BUY'
    trade_information['price'] = candles[1][3]
    trade_information['description'] = 'Long entry signal'
    trade_information['type'] = 'LIMIT'
    trade_information['can_order'] = True
    return trade_information