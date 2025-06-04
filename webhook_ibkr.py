from flask import Flask, request, jsonify
from ib_insync import *
import threading

# Flask app
app = Flask(__name__)

# Global variables
total_contracts = 0
ib = IB()
ib_connected = False

# Lock for shared resources
contracts_lock = threading.Lock()
ib_lock = threading.Lock()

# Define the MNQ (Micro E-mini Nasdaq) Futures Contract
def create_mnq_contract():
    return Future(symbol='MNQ', lastTradeDateOrContractMonth='202506', exchange='CME', currency='USD')

# Function to connect to IBKR
def connect_ibkr():
    with ib_lock:  # Ensure thread-safe connection handling
        if not ib.isConnected():
            try:
                ib.connect('127.0.0.1', 7497, clientId=111, timeout=5)
                print("Connected to IBKR.")
            except Exception as e:
                print(f"API connection failed: {e}")
                return False
    return True

# Place order based on signal
def place_order(signal):
    global total_contracts
    if not connect_ibkr():
        print("Error connecting to IBKR: aborting order.")
        return

    contract = create_mnq_contract()
    ib.qualifyContracts(contract)

    # Get current price to calculate stop
    ticker = ib.reqMktData(contract, '', False, False)
    ib.sleep(.1)
    ib.cancelMktData(contract)
    last_price = ticker.last if ticker.last else ticker.close

    #quantity = 1
    tick_size = 0.25
    stop_ticks = 120
    stop_distance = tick_size * stop_ticks  # = 30 points

    bracket = None
    market = None
    positions = ib.positions()
    ibkr_position = None
    if len(positions) != 0:
        for pos in positions:
            if pos.contract.conId == contract.conId:
                ibkr_position = pos
    with contracts_lock:  # Locking access to total_contracts
        if signal.lower() == 'long entry' and total_contracts < 6 and ibkr_position < 6:
            stop_price = round(last_price - stop_distance, 2)
            total_contracts += 1
            print(f"{total_contracts} contracts held in python before entry")
            bracket = ib.bracketOrder(
                        action='BUY',
                        quantity=1,
                        limitPrice=None,
                        takeProfitPrice=None,
                        stopLossPrice=stop_price
                        )
            bracket[0].orderType = 'MKT'
        elif signal.lower() == 'short entry' and total_contracts > -6 and ibkr_position > -6:
            print(f"{total_contracts} contracts held in python before entry")
            stop_price = round(last_price + stop_distance, 2)
            total_contracts -= 1
            bracket = ib.bracketOrder(
                        action='SELL',
                        quantity=1,
                        limitPrice=None,
                        takeProfitPrice=None,
                        stopLossPrice=stop_price
                        )
            bracket[0].orderType = 'MKT'
        else:
            positions = ib.positions()
            stop_price = None
            for pos in positions:
                if pos.contract.conId == contract.conId:
                    print(f"Holding {pos.position} contracts of {pos.contract.symbol} in ibkr before potential exit")
                    print(f"{total_contracts} in python before potential exit")
                    if signal.lower() == 'long exit' and int(total_contracts) == int(pos.position) and pos.position > 0:
                        market = MarketOrder('SELL', 1)
                        total_contracts -= 1
                    #Checking for manual/ibkr stop loss that hasn't had a signal yet for that stop. Preventing double exit/position reversal, and updating total_contracts to match ibkr.
                    elif signal.lower() == 'long exit' and int(total_contracts) >= int(pos.position) and pos.position > 0:
                        print(f"ibkr stop-out catch up, no exit order placed, total_contracts -1")
                        total_contracts -= 1
                    elif signal.lower() == 'short exit' and int(total_contracts) == int(pos.position) and pos.position < 0:
                        total_contracts += 1
                        market = MarketOrder('BUY', 1)
                    #Checking for manual/ibkr stop loss that hasn't had a signal yet for that stop. Preventing double exit/position reversal, and updating total_contracts to match ibkr.
                    elif signal.lower() == 'short exit' and int(total_contracts) <= int(pos.position) and pos.position < 0:
                        print(f"ibkr stop-out catch up, no exit order placed, total_contracts +1")
                        total_contracts += 1
                    else:
                        print(f"Invalid signal: {signal}")
                        return

    # Place both orders
    if bracket is not None:
        bracket[0].outsideRth = True
        ib.placeOrder(contract, bracket[0])
        print(f"Placed bracket order: {signal.upper()}")
        if bracket.stopLoss is not None:
            bracket[2].outsideRth = True
            ib.placeOrder(contract, bracket[2])
            print(f"Stop @ {stop_price}")
        #TP Untested
        if bracket.takeProfit is not None:
            bracket[1].outsideRth = True
            ib.placeorder(contract, bracket[1])
            print("TP @...Take Profit")
    elif market is not None:
        ib.placeOrder(contract, market)
        print(f"Placed market order: {signal.upper()}")
        open_orders = ib.openOrders()

        # Filter stop loss orders
        stop_orders = [o for o in open_orders if o.orderType == 'STP']

        if stop_orders:
            # Cancel most recent open stop
            most_recent_stop = max(stop_orders, key=lambda t: t.orderId)
            ib.cancelOrder(most_recent_stop)  # Cancel the underlying order
            print(f"Canceled stop loss order ID: {most_recent_stop.orderId}")
        else:
            print("No open stop loss orders found.")
    ib.sleep(.1)

# Flask endpoint to receive TradingView webhook alerts
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or 'signal' not in data:
        return jsonify({'error': 'Invalid payload'}), 400

    signal = data['signal']
    print(f"Received signal: {signal}")

    # Run place_order function directly (this is thread-safe now)
    place_order(signal)

    return jsonify({'status': f'Order for {signal} received'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=False, processes=1)


# from flask import Flask, request, jsonify
# from ib_insync import *
# import threading
# import asyncio
# import random
# import queue

# # Flask app
# app = Flask(__name__)

# total_contracts = 0
# #contracts_lock = threading.Lock()

# ib = IB()
# #ib_lock = threading.Lock()
# ib_connected = False

# #order_queue = queue.Queue()

# # Define the MNQ (Micro E-mini Nasdaq) Futures Contract
# def create_mnq_contract():
#     return Future(symbol='MNQ', lastTradeDateOrContractMonth='', exchange='CME', currency='USD')

# # Function to connect to IBKR (inside the thread)
# def connect_ibkr():
#     #with ib_lock:
#     try:
#         asyncio.get_running_loop()
#     except RuntimeError:
#         asyncio.set_event_loop(asyncio.new_event_loop())
#     if not ib.isConnected():
#         try:
#             ib.connect('127.0.0.1', 7497, clientId=111, timeout=5)
#         except Exception as e:
#             print(f"API connection failed: {e}")
#             return False
#     return True
#     # global ib_connected
#     # if not ib_connected:
#     #     if not ib.isConnected():
#     #         print("Connecting to IBKR...")
#     #         ib.connect('127.0.0.1', 7497, clientId=111, timeout = 5)
#     #         ib_connected = True
#     # return ib
    

# # Place order based on signal
# # Checks ibkr contracts vs current total contract count to ensure a manual 
# def place_order(signal):
#     global total_contracts
#     #asyncio.set_event_loop(asyncio.new_event_loop())
#     # Create a new event loop for this thread
#     # loop = asyncio.new_event_loop()
#     # asyncio.set_event_loop(loop)
#     if not connect_ibkr():
#         print("Error connecting to IBKR: aborting order.")
#         return
#     contract = Future(symbol='MNQ', lastTradeDateOrContractMonth='202506', exchange='CME', currency='USD')
#     ib.qualifyContracts(contract)

#     # Get current price to calculate stop
#     ticker = ib.reqMktData(contract, '', False, False)
#     ib.sleep(1)
#     ib.cancelMktData(contract)
#     last_price = ticker.last if ticker.last else ticker.close

#     quantity = 1
#     tick_size = 0.25
#     stop_ticks = 120
#     stop_distance = tick_size * stop_ticks  # = 30 points

#     # parent_order = None
#     # stop_order = None
#     bracket = None
#     market = None

#     if signal.lower() == 'long entry' and total_contracts < 6:
#         #parent_order = MarketOrder('BUY', quantity, transmit=False)
#         stop_price = round(last_price - stop_distance, 2)
#         # stop_order = StopOrder('SELL', quantity, stop_price, parentId=parent_order.orderId, transmit=True)
#         #with contracts_lock:
#         total_contracts += 1
#         bracket = ib.bracketOrder(
#                     action='BUY',
#                     quantity=1,
#                     limitPrice=None,             # Market order
#                     takeProfitPrice=None,        # No TP
#                     stopLossPrice=stop_price     # 120 tick SL
#                     )   
#         bracket[0].orderType = 'MKT'
#     elif signal.lower() == 'short entry' and total_contracts > -6:
#         #parent_order = MarketOrder('SELL', quantity, transmit=False)
#         stop_price = round(last_price + stop_distance, 2)
#         #stop_order = StopOrder('BUY', quantity, stop_price, parentId=parent_order.orderId, transmit=True)
#         #with contracts_lock:
#         total_contracts -= 1
#         bracket = ib.bracketOrder(
#                     action='SELL',
#                     quantity=1,
#                     limitPrice=None,             # Market order
#                     takeProfitPrice=None,        # No TP
#                     stopLossPrice=stop_price     # 120 tick SL
#                     )
#         bracket[0].orderType = 'MKT'
#     else:
#         positions = ib.positions()
#         stop_price = None
#         for pos in positions:
#             if pos.contract.conId == contract.conId:
#                 print(f"Holding {pos.position} contracts of {pos.contract.symbol} in ibkr")
#                 print("{total_contracts} in python")
#                 if signal.lower() == 'long exit' and int(total_contracts) == int(pos.position) and total_contracts > 0:
#                     #parent_order = MarketOrder('SELL', 1)
#                     market = MarketOrder('SELL', 1)
#                     #with contracts_lock:
#                     total_contracts -= 1
#                 #Checking for manual/ibkr stop loss that hasn't had a signal yet for that stop. Preventing double exit/position reversal, and updating total_contracts to match ibkr.
#                 elif signal.lower() == 'long exit' and int(total_contracts) >= int(pos.position) and total_contracts > 0:
#                     #with contracts_lock:
#                     total_contracts -= 1
#                 elif signal.lower() == 'short exit' and int(total_contracts) == int(pos.position) and total_contracts < 0:
#                     #parent_order = MarketOrder('BUY', 1)
#                     #with contracts_lock:
#                     total_contracts += 1
#                     market = MarketOrder('BUY', 1)
#                 #Checking for manual/ibkr stop loss that hasn't had a signal yet for that stop. Preventing double exit/position reversal, and updating total_contracts to match ibkr.
#                 elif signal.lower() == 'short exit' and int(total_contracts) <= int(pos.position) and total_contracts < 0:
#                     #with contracts_lock:
#                     total_contracts += 1
#                 else:
#                     print(f"Invalid signal: {signal}")
#                     return

#     # Place both orders
#     if bracket is not None:
#         bracket[0].outsideRth = True
#         ib.placeOrder(contract, bracket[0])
#         print(f"Placed bracket order: {signal.upper()}")
#         if bracket.stopLoss is not None:
#             bracket[2].outsideRth = True
#             ib.placeOrder(contract, bracket[2])
#             print(f"Stop @ {stop_price}")
#     elif market is not None:
#         ib.placeOrder(contract, market)
#         print(f"Placed market order: {signal.upper()}")
#         open_orders = ib.openOrders()

#         # Filter stop loss orders
#         stop_orders = [o for o in open_orders if o.orderType == 'STP']

#         if stop_orders:
#             #Cancel most recent open stop
#             most_recent_stop = max(stop_orders, key=lambda t: t.orderId)
#             ib.cancelOrder(most_recent_stop)  # Cancel the underlying order
#             print(f"Canceled stop loss order ID: {most_recent_stop.orderId}")
#         else:
#             print("No open stop loss orders found.")

#     ib.sleep(1)

# # def run_with_loop(fn, *args, **kwargs):
# #     loop = asyncio.new_event_loop()
# #     asyncio.set_event_loop(loop)
# #     return fn(*args, **kwargs)

# # Flask endpoint to receive TradingView webhook alerts
# @app.route('/webhook', methods=['POST'])
# def webhook():
#     data = request.get_json()
#     if not data or 'signal' not in data:
#         return jsonify({'error': 'Invalid payload'}), 400

#     signal = data['signal']
#     print(f"Received signal: {signal}")
#     #order_queue.put(signal)

#     place_order(signal)
#     # Run IBKR order in background to not block the server
#     #threading.Thread(target=place_order, args=(signal,)).start()
#     #threading.Thread(target=run_with_loop, args=(place_order, signal)).start()
#     #return jsonify({'status': f'Order for {signal} enqueued'}), 200
#     return jsonify({'status': f'Order for {signal} received'}), 200

# # def order_worker():
# #     while True:
# #         signal = order_queue.get()
# #         try:
# #             place_order(signal)
# #         except Exception as e:
# #             print(f"❌ Error while placing order: {e}")
# #         finally:
# #             order_queue.task_done()

# if __name__ == '__main__':
#     #threading.Thread(target=order_worker, daemon=True).start()
#     app.run(host='0.0.0.0', port=5002, debug=False, threaded=False, processes=1)

#Original GPT output for stoploss
# def place_order(signal):
#     # Create a new event loop for this thread
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)

#     ib = IB()
#     ib.connect('127.0.0.1', 7497, clientId=1)

#     contract = Future(symbol='MNQ', lastTradeDateOrContractMonth='202506', exchange='CME', currency='USD')
#     ib.qualifyContracts(contract)

#     if signal.lower() == 'buy':
#         order = MarketOrder('BUY', 1)
#     elif signal.lower() == 'sell':
#         order = MarketOrder('SELL', 1)
#     else:
#         print(f"Invalid signal: {signal}")
#         ib.disconnect()
#         return

#     trade = ib.placeOrder(contract, order)
#     ib.sleep(1)  # Let IBKR process the order

#     print(f"Order status: {trade.orderStatus.status}")
#     ib.disconnect()