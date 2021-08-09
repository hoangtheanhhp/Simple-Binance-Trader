#! /usr/bin/env python3
import os
import sys
import copy
import time
import logging
import datetime
import threading
import trader_configuration as TC

MULTI_DEPTH_INDICATORS = ['ema', 'sma', 'rma']

# Base commission fee with binance.
COMMISION_FEE = 0.1

# Base layout for market pricing.
BASE_TRADE_PRICE_LAYOUT = {
    'lastPrice': 0,  # Last price seen for the market.
    'askPrice': 0,  # Last ask price seen for the market.
    'bidPrice': 0  # Last bid price seen for the market.
}

# Base layout for trader state.
BASE_STATE_LAYOUT = {
    'base_currency': 0.0,  # The base mac value used as referance.
    'force_sell': False,  # If the trader should dump all tokens.
    'runtime_state': None,  # The state that actual trader object is at.
    'last_update_time': 0  # The last time a full look of the trader was completed.
}

# Base layout used by the trader.
BASE_MARKET_LAYOUT = {
    'can_order': False,  # If the bot is able to trade in the current market.
    'price': 0.0,  # The price related to BUY.
    'buy_price': 0.0,  # Buy price of the asset.
    'stopPrice': 0.0,  # The stopPrice relate
    'stopLimitPrice': 0.0,  # The stopPrice relate
    'tokens_holding': 0.0,  # Amount of tokens being held.
    'order_point': None,  # Used to visulise complex stratergy progression points.
    'id': None,  # The ID that is tied to the placed order.
    'status': 'WAIT',  # The type of the order that is placed
    'side': 'BUY',  # The status of the current order.
    'type': 'LIMIT',  # Used to show the type of order (SIGNAL/STOP-LOSS/WAIT)
    'description': 0,  # The description of the order.
    'order_market_type': None,  # The market type of the order placed.
    'market_status': None,  # Last state the market trader is.
    'quantity': 0,
}


class BaseTrader(object):
    def __init__(self, quote_asset, base_asset, rest_api, socket_api=None, data_if=None):
        # Initilize the main trader object.
        symbol = '{0}{1}'.format(quote_asset, base_asset)

        # Easy printable format for market symbol.
        self.print_pair = '{0}-{1}'.format(quote_asset, base_asset)
        self.quote_asset = quote_asset
        self.base_asset = base_asset

        logging.info('[BaseTrader][{0}] Initilizing trader object and empty attributes.'.format(self.print_pair))

        # Sets the rest api that will be used by the trader.
        self.rest_api = rest_api

        if socket_api is None and data_if is None:
            logging.critical(
                '[BaseTrader][{0}] Initilization failed, bot must have either socket_api OR data_if set.'.format(
                    self.print_pair))
            return

        # Setup socket/data interface.
        self.data_if = None
        self.socket_api = None

        if socket_api:
            # Setup socket for live market data trading.
            self.candle_enpoint = socket_api.get_live_candles
            self.depth_endpoint = socket_api.get_live_depths
            self.socket_api = socket_api
        else:
            # Setup data interface for past historic trading.
            self.data_if = data_if
            self.candle_enpoint = data_if.get_candle_data
            self.depth_endpoint = data_if.get_depth_data

        # Setup the default path for the trader by market beeing traded.
        self.orders_log_path = 'logs/order_{0}_log.txt'.format(symbol)
        self.configuration = {}
        self.market_prices = {}
        self.wallet_pair = None
        self.indicators = {}
        self.activity = {}
        self.trade_recorder = []
        self.state_data = {}
        self.rules = {}
        self.last_order = None
        self.order = None

        logging.debug('[BaseTrader][{0}] Initilized trader object.'.format(self.print_pair))

    def setup_initial_values(self, trading_type, run_type, filters):
        # Initilize trader values.
        logging.info('[BaseTrader][{0}] Initilizing trader object attributes with data.'.format(self.print_pair))

        # Populate required settings.
        self.configuration.update({
            'trading_type': trading_type,
            'run_type': run_type,
            'base_asset': self.base_asset,
            'quote_asset': self.quote_asset,
            'symbol': '{0}{1}'.format(self.base_asset, self.quote_asset)
        })
        self.rules.update(filters)

        # Initilize default values.
        self.activity.update(copy.deepcopy(BASE_MARKET_LAYOUT))
        self.market_prices.update(copy.deepcopy(BASE_TRADE_PRICE_LAYOUT))
        self.state_data.update(copy.deepcopy(BASE_STATE_LAYOUT))

        logging.debug('[BaseTrader][{0}] Initilized trader attributes with data.'.format(self.print_pair))

    def start(self, MAC, wallet_pair, open_orders=None):
        '''
        Start the trader.
        Requires: MAC (Max Allowed Currency, the max amount the trader is allowed to trade with in BTC).
        -> Check for previous trade.
            If a recent, not closed traded is seen, or leftover currency on the account over the min to place order then set trader to sell automatically.
        
        ->  Start the trader thread. 
            Once all is good the trader will then start the thread to allow for the market to be monitored.
        '''
        logging.info('[BaseTrader][{0}] Starting the trader object.'.format(self.print_pair))
        sock_symbol = self.base_asset + self.quote_asset

        if not self.socket_api:
            while True:
                if self.socket_api.get_live_candles()[sock_symbol] and (
                        'a' in self.socket_api.get_live_depths()[sock_symbol]):
                    break

        self.state_data['runtime_state'] = 'SETUP'
        self.wallet_pair = wallet_pair
        self.state_data['base_currency'] = float(MAC)

        # Start the main of the trader in a thread.
        threading.Thread(target=self._main).start()
        return True

    def stop(self):
        ''' 
        Stop the trader.
        -> Trader cleanup.
            To gracefully stop the trader and cleanly eliminate the thread as well as market orders.
        '''
        logging.debug('[BaseTrader][{0}] Stopping trader.'.format(self.print_pair))

        self.state_data['runtime_state'] = 'STOP'
        return True

    def _main(self):
        '''
        Main body for the trader loop.
        -> Wait for candle data to be fed to trader.
            Infinite loop to check if candle has been populated with data,
        -> Call the updater.
            Updater is used to re-calculate the indicators as well as carry out timed checks.
        -> Call Order Manager.
            Order Manager is used to check on currently PLACED orders.
        -> Call Trader Manager.
            Trader Manager is used to check the current conditions of the indicators then set orders if any can be PLACED.
        '''
        sock_symbol = self.base_asset + self.quote_asset
        last_wallet_update_time = 0

        market_type = 'LONG'
        if self.configuration['trading_type'] == 'SPOT':
            market_type = 'LONG'

        # Main trader loop
        while self.state_data['runtime_state'] != 'STOP':
            # Pull required data for the trader.
            candles = self.candle_enpoint(sock_symbol)
            books_data = self.depth_endpoint(sock_symbol)
            self.indicators = TC.technical_indicators(candles)
            indicators = self.strip_timestamps(self.indicators)

            logging.debug('[BaseTrader] Collected trader data. [{0}]'.format(self.print_pair))

            socket_buffer_symbol = None
            if sock_symbol in self.socket_api.socketBuffer:
                socket_buffer_symbol = self.socket_api.socketBuffer[sock_symbol]

            # get the global socket buffer and update the wallets for the used markets.
            socket_buffer_global = self.socket_api.socketBuffer
            if 'outboundAccountPosition' in socket_buffer_global:
                if last_wallet_update_time != socket_buffer_global['outboundAccountPosition']['E']:
                    self.wallet_pair, last_wallet_update_time = self.update_wallets(socket_buffer_global)
            ## For managing active orders.
            self.activity = self._order_status_manager()
            # Update martket prices with current data
            if not books_data:
                self.market_prices = {
                    'lastPrice': candles[0][4],
                    'askPrice': books_data['a'][0][0],
                    'bidPrice': books_data['b'][0][0]}

            # Check to make sure there is enough crypto to place orders.
            if self.state_data['runtime_state'] == 'PAUSE_INSUFBALANCE':
                if self.wallet_pair[self.quote_asset][0] > self.state_data['base_currency']:
                    self.state_data['runtime_state'] = 'RUN'

            if not self.state_data['runtime_state'] in ['STANDBY', 'FORCE_STANDBY', 'FORCE_PAUSE']:
                # Call for custom conditions that can be used for more advanced managemenet of the trader.
                # For managing the placement of orders/condition checking.
                if self.state_data['runtime_state'] == 'RUN':
                    if self.activity['status'] == 'COMPLETE':
                        self.activity['status'] = 'WAIT'
                    self._trade_manager(market_type, indicators, candles)

            time.sleep(1)

            current_localtime = time.localtime()
            self.state_data['last_update_time'] = '{0}:{1}:{2}'.format(current_localtime[3], current_localtime[4],
                                                                       current_localtime[5])

            if self.state_data['runtime_state'] == 'SETUP':
                self.state_data['runtime_state'] = 'RUN'

    def _trade_manager(self, market_type, indicators, candles):
        ''' 
        Here both the sell and buy conditions are managed by the trader.
        -> Manager Sell Conditions.
            Manage the placed sell condition as well as monitor conditions for the sell side.
        -> Manager Buy Conditions.
            Manage the placed buy condition as well as monitor conditions for the buy side.
        -> Place Market Order.
            Place orders on the market with real and assume order placemanet with test.
        '''
        # Set the consitions to look over.
        if self.activity['side'] == 'SELL':
            current_conditions = TC.long_exit_conditions
        else:
            if self.state_data['runtime_state'] == 'FORCE_PREVENT_BUY' or self.activity['status'] == 'LOCKED':
                return
            current_conditions = TC.long_entry_conditions

        logging.debug(
            '[BaseTrader] Checking for {0} {1} condition. [{2}]'.format(self.activity['side'], market_type,
                                                                        self.print_pair))
        new_order = current_conditions(self.activity, indicators, self.market_prices, candles,
                                       self.print_pair)

        # If no order is to be placed just return.
        if not new_order:
            return

        if new_order['status'] == 'WAIT':
            return
        elif new_order['status'] == 'COMPLETE':
            if self.activity['side'] == 'BUY':
                self.activity['side'] = 'SELL'
            else:
                self.activity['side'] = 'BUY'
            self.activity['status'] = 'WAIT'
            return
        else:
            # Format the prices to be used.
            if 'price' in new_order:
                if 'price' in new_order:
                    new_order['price'] = '{0:.{1}f}'.format(float(new_order['price']), self.rules['TICK_SIZE'])
                if 'stopPrice' in new_order:
                    new_order['stopPrice'] = '{0:.{1}f}'.format(float(new_order['stopPrice']), self.rules['TICK_SIZE'])
            # If order is to be placed or updated then do so.
            self.activity = new_order
            if self.activity['side'] == 'BUY':
                self.activity['quantity'] = '{0:.{1}f}'.format(
                    float(self.state_data['base_currency'] / float(self.activity['price'])), self.rules['LOT_SIZE'])
        # Place Market Order.
        if self._condition_to_order():
            order_results = self._place_order()
            logging.debug('order: {0}\norder result:\n{1}'.format(self.activity, order_results))

            # If errors are returned for the order then sort them.
            if 'code' in order_results['data']:
                # used to catch error codes.
                if order_results['data']['code'] == -2010:
                    self.state_data['runtime_state'] = 'PAUSE_INSUFBALANCE'
                elif order_results['data']['code'] == -2011:
                    self.state_data['runtime_state'] = 'CHECK_ORDERS'
                return
            self.order = self.activity
            self.order['status'] = 'PLACED'
            self.order['price'] = order_results['data']['price']
            self.order['id'] = order_results['data']['orderId']
            logging.info('[BaseTrader] {0} Order placed for {1}.'.format(self.print_pair, new_order['type']))
            logging.info(
                '[BaseTrader] {0} Order placement results:\n{1}'.format(self.print_pair, str(order_results['data'])))

    def _condition_to_order(self):
        return True
        if self.activity:
            order = self.activity
            if float(order['price']) > self.rules['PRICE']['price_ceiling']:
                return False
            return True
        return False

    def _place_order(self):
        ''' place order '''

        # Place orders for both SELL/BUY sides for both TEST/REAL run types.
        rData = {}
        order = self.activity
        side = order['side']

        if order['type'] == 'OCO_LIMIT':
            logging.info(
                '[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3} price:{4}, stopPrice:{5}, stopLimitPrice:{6}'.format(
                    self.print_pair, order['side'], order['type'], order['quantity'], order['price'],
                    order['stopPrice'], order['stopLimitPrice']))
            rData.update(
                self.rest_api.place_order(self.configuration['trading_type'], symbol=self.configuration['symbol'],
                                          side=side, type=order['type'], timeInForce='GTC',
                                          quantity=order['quantity'], price=order['price'],
                                          stopPrice=order['stopPrice'],
                                          stopLimitPrice=order['stopLimitPrice']))
            return ({'action': 'PLACED_MARKET_ORDER', 'data': rData})

        elif order['type'] == 'MARKET':
            logging.info(
                '[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3}'.format(self.print_pair, order['side'],
                                                                                   order['type'],
                                                                                   order['quantity']))
            rData.update(
                self.rest_api.place_order(self.configuration['trading_type'], symbol=self.configuration['symbol'],
                                          side=side, type=order['type'], quantity=order['quantity']))
            return ({'action': 'PLACED_MARKET_ORDER', 'data': rData})

        elif order['type'] == 'LIMIT':
            logging.info(
                '[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3} price:{4}'.format(self.print_pair,
                                                                                             order['side'],
                                                                                             order['type'],
                                                                                             order['quantity'],
                                                                                             order['price']))
            rData.update(
                self.rest_api.place_order(self.configuration['trading_type'], symbol=self.configuration['symbol'],
                                          side=side, type=order['type'], timeInForce='GTC',
                                          quantity=order['quantity'], price=order['price']))
            return {'action': 'PLACED_LIMIT_ORDER', 'data': rData}

        elif order['type'] == 'STOP_LOSS_LIMIT':
            logging.info(
                '[BaseTrader] symbol:{0}, side:{1}, type:{2}, quantity:{3} price:{4}, stopPrice:{5}'.format(
                    self.print_pair, order['side'], order['type'], order['quantity'], order['price'],
                    order['stopPrice']))
            rData.update(
                self.rest_api.place_order(self.configuration['trading_type'], symbol=self.configuration['symbol'],
                                          side=side, type=order['type'], timeInForce='GTC',
                                          quantity=order['quantity'], price=order['price'],
                                          stopPrice=order['stopPrice']))
            return {'action': 'PLACED_STOPLOSS_ORDER', 'data': rData}

    def _cancel_order(self, order_id):
        ''' cancel orders '''
        cancel_order_result = self.rest_api.cancel_order(self.configuration['trading_type'],
                                                         symbol=self.configuration['symbol'], orderId=order_id)
        logging.debug('[BaseTrader] {0} cancel order results:\n{1}'.format(self.print_pair, cancel_order_result))
        return cancel_order_result

    def get_trader_data(self):
        ''' Access that is availble for the traders details. '''
        trader_data = {
            'market': self.print_pair,
            'configuration': self.configuration,
            'market_prices': self.market_prices,
            'wallet_pair': self.wallet_pair,
            'activity': self.activity,
            'trade_recorder': self.trade_recorder,
            'state_data': self.state_data,
            'rules': self.rules
        }

        return trader_data

    def strip_timestamps(self, indicators):

        base_indicators = {}

        for ind in indicators:
            if ind in MULTI_DEPTH_INDICATORS:
                base_indicators.update({ind: {}})
                for sub_ind in indicators[ind]:
                    base_indicators[ind].update({sub_ind: [val[1] for val in indicators[ind][sub_ind]]})
            else:
                base_indicators.update({ind: [val[1] for val in indicators[ind]]})

        return base_indicators

    def update_wallets(self, socket_buffer_global):
        ''' Update the wallet data with that collected via the socket '''
        last_wallet_update_time = socket_buffer_global['outboundAccountPosition']['E']
        foundBase = False
        foundQuote = False
        wallet_pair = {}

        for wallet in socket_buffer_global['outboundAccountPosition']['B']:
            if wallet['a'] == self.base_asset:
                wallet_pair.update({self.base_asset: [float(wallet['f']), float(wallet['l'])]})
                foundBase = True
            elif wallet['a'] == self.quote_asset:
                wallet_pair.update({self.quote_asset: [float(wallet['f']), float(wallet['l'])]})
                foundQuote = True

            if foundQuote and foundBase:
                break

        if not (foundBase):
            wallet_pair.update({self.base_asset: [0.0, 0.0]})
        if not (foundQuote):
            wallet_pair.update({self.quote_asset: [0.0, 0.0]})

        logging.info('[BaseTrader] New account data pulled, wallets updated. [{0}]'.format(self.print_pair))
        return (wallet_pair, last_wallet_update_time)

    def _order_status_manager(self):
        '''
        This is the manager for all and any active orders.
        -> Check orders (Test/Real).
            This checks both the buy and sell side for test orders and updates the trader accordingly.
        -> Monitor trade outcomes.
            Monitor and note down the outcome of trades for keeping track of progress.
        '''
        order = self.rest_api.get_order(self.configuration['trading_type'], symbol=self.configuration['symbol'],
                                        orderId=self.order['id'])
        trade_done = False
        if order['origQty'] == order['executedQty']:
            trade_done = True
        cp = self.order
        if trade_done:
            # Update order recorder.
            self.trade_recorder.append(
                [time.time(), cp['price'], cp['quantity'], cp['description'], cp['side']])
            logging.info('[BaseTrader] Completed {0} order. [{1}]'.format(cp['side'], self.print_pair))

            if self.order['side'] == 'SELL':
                # Format data to print it to a file.
                trB = self.trade_recorder[-2]
                trS = self.trade_recorder[-1]

                buyTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trB[0]))
                sellTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trS[0]))

                outcome = ((trS[1] - trB[1]) * trS[2])

                trade_details = 'BuyTime:{0}, BuyPrice:{1:.8f}, BuyQuantity:{2:.8f}, BuyType:{3}, SellTime:{4}, SellPrice:{5:.8f}, SellQuantity:{6:.8f}, SellType:{7}, Outcome:{8:.8f}\n'.format(
                    buyTime, trB[1], trB[2], trB[3], sellTime, trS[1], trS[2], trS[3],
                    outcome)  # (Sellprice - Buyprice) * tokensSold
                with open(self.orders_log_path, 'a') as file:
                    file.write(trade_details)

                # Reset trader variables.
                cp['side'] = 'BUY'
                cp['status'] = None

        return cp
