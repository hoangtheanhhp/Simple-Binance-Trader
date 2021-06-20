import logging
import numpy as np
import technical_indicators as TI

# Minimum price rounding.
pRounding = 8


def technical_indicators(candles):
    indicators = {}

    time_values = [candle[0] for candle in candles]
    open_prices = [candle[1] for candle in candles]
    high_prices = [candle[2] for candle in candles]
    low_prices = [candle[3] for candle in candles]
    close_prices = [candle[4] for candle in candles]

    indicators.update({'macd': TI.get_MACD(close_prices, time_values=time_values, map_time=True)})

    indicators.update({'ema': {}})
    indicators['ema'].update({'ema200': TI.get_EMA(close_prices, 200, time_values=time_values, map_time=True)})

    return indicators


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


def long_entry_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    # Place Long entry (buy) conditions under this section.
    trade_information['side'] = 'BUY'
    trade_information['price'] = prices['bidPrice']
    trade_information['description'] = 'Long entry signal'
    trade_information['order_type'] = 'LIMIT'
    return trade_information


def short_exit_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    # Place Short exit (sell) conditions under this section.
    pass


def short_entry_conditions(custom_conditional_data, trade_information, indicators, prices, candles, symbol):
    # Place Short entry (buy) conditions under this section.
    pass
