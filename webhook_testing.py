# from flask import Flask, request, jsonify
# from ib_insync import *
# import threading
# import asyncio

# # Flask app
# app = Flask(__name__)

# # Global variables
# total_contracts = 0
# ib = IB()
# ib_connected = False

# # Locks for shared resources
# contracts_lock = threading.Lock()
# ib_lock = threading.Lock()

# # Define the MNQ (Micro E-mini Nasdaq) Futures Contract
# def create_mnq_contract():
#     return Future(symbol='MNQ', lastTradeDateOrContractMonth='202506', exchange='CME', currency='USD')

# # Function to connect to IBKR
# def connect_ibkr():
#     with ib_lock:  # Ensure thread-safe connection handling
#         if not ib.isConnected():
#             try:
#                 # Create a new event loop for the thread
#                 loop = asyncio.new_event_loop()
#                 asyncio.set_event_loop(loop)
#                 ib.connect('127.0.0.1', 7497, clientId=111, timeout=5)
#                 ib.client.reqIds(1)
#                 print("Connected to IBKR.")
#             except Exception as e:
#                 print(f"API connection failed: {e}")
#                 return False
#     return True

# # Thread-safe function to place orders
# def place_order(signal):
#     global total_contracts

#     if not connect_ibkr():
#         print("Error connecting to IBKR: aborting order.")
#         return

#     try:
#         asyncio.get_running_loop()
#     except RuntimeError:
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)

#     if not connect_ibkr():
#         print("Error connecting to IBKR: aborting order.")
#         return
#     contract = create_mnq_contract()

#     with ib_lock:
#         ib.qualifyContracts(contract)
#         ticker = ib.reqMktData(contract, '', False, False)
#         ib.sleep(0.1)
#         ib.cancelMktData(contract)
#         last_price = ticker.last if ticker.last else ticker.close

#         positions = ib.positions()
#         ibkr_position = 0
#         for pos in positions:
#             if pos.contract.conId == contract.conId:
#                 ibkr_position = pos.position

#     tick_size = 0.25
#     stop_ticks = 120
#     stop_distance = tick_size * stop_ticks  # = 30 points
#     bracket = None
#     market = None

#     with contracts_lock:
#         if signal.lower() == 'long entry' and total_contracts < 6 and ibkr_position < 6:
#             stop_price = round(last_price - stop_distance, 2)
#             total_contracts += 1
#             print(f"{total_contracts} contracts held in python before entry")
#             bracket = ib.bracketOrder(
#                 action='BUY',
#                 quantity=1,
#                 limitPrice=None,
#                 takeProfitPrice=None,
#                 stopLossPrice=stop_price
#             )
#             bracket[0].orderType = 'MKT'

#         elif signal.lower() == 'short entry' and total_contracts > -6 and ibkr_position > -6:
#             stop_price = round(last_price + stop_distance, 2)
#             total_contracts -= 1
#             print(f"{total_contracts} contracts held in python before entry")
#             bracket = ib.bracketOrder(
#                 action='SELL',
#                 quantity=1,
#                 limitPrice=None,
#                 takeProfitPrice=None,
#                 stopLossPrice=stop_price
#             )
#             bracket[0].orderType = 'MKT'

#         else:
#             for pos in positions:
#                 if pos.contract.conId == contract.conId:
#                     print(f"Holding {pos.position} contracts of {pos.contract.symbol} in ibkr before potential exit")
#                     print(f"{total_contracts} in python before potential exit")

#                     if signal.lower() == 'long exit' and int(total_contracts) == int(pos.position) and pos.position > 0:
#                         market = MarketOrder('SELL', 1)
#                         total_contracts -= 1
#                     elif signal.lower() == 'long exit' and int(total_contracts) >= int(pos.position) and pos.position > 0:
#                         print(f"ibkr stop-out catch up, no exit order placed, total_contracts -1")
#                         total_contracts -= 1
#                     elif signal.lower() == 'short exit' and int(total_contracts) == int(pos.position) and pos.position < 0:
#                         total_contracts += 1
#                         market = MarketOrder('BUY', 1)
#                     elif signal.lower() == 'short exit' and int(total_contracts) <= int(pos.position) and pos.position < 0:
#                         print(f"ibkr stop-out catch up, no exit order placed, total_contracts +1")
#                         total_contracts += 1
#                     elif (signal.lower() == 'short exit' and int(total_contracts) > int(pos.position)) or \
#                          (signal.lower() == 'long exit' and int(total_contracts) < int(pos.position)):
#                         print(f"Can't exit, short & python position > ibkr or long & python < ibkr")
#                         return
#                     elif (signal.lower() == 'short exit' or signal.lower() == 'long exit') and \
#                          (pos.position == 0 or total_contracts == 0):
#                         print("Can't exit on 0 position in ibkr or python")
#                         return
#                     else:
#                         print(f"Invalid signal: {signal}")
#                         return

#     with ib_lock:
#         if bracket is not None:
#             bracket[0].outsideRth = True
#             ib.placeOrder(contract, bracket[0])
#             print(f"Placed bracket order: {signal.upper()}")
#             if bracket.stopLoss is not None:
#                 bracket[2].outsideRth = True
#                 ib.placeOrder(contract, bracket[2])
#                 print(f"Stop @ {stop_price}")
#         elif market is not None:
#             ib.placeOrder(contract, market)
#             print(f"Placed market order: {signal.upper()}")

#             open_orders = ib.openOrders()
#             stop_orders = [o for o in open_orders if o.orderType == 'STP']
#             if stop_orders:
#                 most_recent_stop = max(stop_orders, key=lambda t: t.orderId)
#                 ib.cancelOrder(most_recent_stop)
#                 print(f"Canceled stop loss order ID: {most_recent_stop.orderId}")
#             else:
#                 print("No open stop loss orders found.")

#         ib.sleep(0.1)

# # Flask endpoint to receive TradingView webhook alerts
# @app.route('/webhook', methods=['POST'])
# def webhook():
#     data = request.get_json()
#     if not data or 'signal' not in data:
#         return jsonify({'error': 'Invalid payload'}), 400

#     signal = data['signal']
#     print(f"Received signal: {signal}")

#     # Handle the signal in a background thread
#     threading.Thread(target=place_order, args=(signal,), daemon=True).start()

#     return jsonify({'status': f'Order for {signal} received'}), 200

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)


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
    return Future(symbol='MNQ', lastTradeDateOrContractMonth='202509', exchange='CME', currency='USD')

# Function to connect to IBKR
def connect_ibkr():
    with ib_lock:  # Ensure thread-safe connection handling
        if not ib.isConnected():
            try:
                #Change 7497 to 7496 for live trading.
                ib.connect('127.0.0.1', 7496, clientId=111, timeout=5)
                ib.client.reqIds(1)
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
    ibkr_position = 0
    if len(positions) != 0:
        for pos in positions:
            if pos.contract.conId == contract.conId:
                ibkr_position = pos.position

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
        elif signal.lower() == 'End of Day' and total_contracts < 0 and ibkr_position < 0:
            market = MarketOrder('BUY', 1)
            total_contracts += 1
        elif signal.lower() == 'End of Day' and total_contracts > 0 and ibkr_position > 0:
            market = MarketOrder('SELL', 1)
            total_contracts -= 1
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
                    elif (signal.lower() == 'short exit' and int(total_contracts) > int(pos.position)) or (signal.lower() == 'long exit' and int(total_contracts) < int(pos.position)):
                        print(f"Can't exit, short & python position > ibkr or long & python < ibkr")
                        return
                    elif (signal.lower() == 'short exit' or signal.lower() == 'long exit') and (pos.position == 0 or total_contracts == 0):
                        print("Can't exit on 0 position in ibkr or python")
                    else:
                        print(f"Invalid signal: {signal}")
                        return

    # Place both orders
    if bracket is not None:
        bracket[0].outsideRth = True
        ib.placeOrder(contract, bracket[0])
        print(f"Placed bracket order: {signal.upper()}\n")
        if bracket.stopLoss is not None:
            bracket[2].outsideRth = True
            ib.placeOrder(contract, bracket[2])
            print(f"Stop @ {stop_price}\n")
        #TP Untested. yields an error if you leave as None and have this uncommented.
        # if bracket.takeProfit is not None:
        #     bracket[1].outsideRth = True
        #     ib.placeOrder(contract, bracket[1])
        #     print("TP @...Take Profit")
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
            print(f"Canceled stop loss order ID: {most_recent_stop.orderId}\n")
        else:
            print("No open stop loss orders found.\n")
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