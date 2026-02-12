from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_socketio import SocketIO, emit
import threading
import time
import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
import requests
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'b3c4f17552b399a339b71fef5c5af905')
socketio = SocketIO(app, cors_allowed_origins="*")

@dataclass
class StockThreshold:
    symbol: str
    upper_limit: Optional[float] = None
    lower_limit: Optional[float] = None
    last_alert_upper: bool = False
    last_alert_lower: bool = False

class NSEStockMonitor:
    def __init__(self, config_file: str = "stock_config.json"):
        self.config_file = config_file
        self.stocks: Dict[str, StockThreshold] = {}
        self.base_url = "https://www.nseindia.com/api/quote-equity"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.monitoring_active = False
        self.monitoring_thread = None
        self.load_config()
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    for symbol, data in config.items():
                        self.stocks[symbol] = StockThreshold(**data)
                logger.info(f"Loaded {len(self.stocks)} stocks from configuration")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self.stocks = {}
    
    def save_config(self):
        config = {}
        for symbol, threshold in self.stocks.items():
            config[symbol] = asdict(threshold)
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuration saved to {self.config_file}")
    
    def add_stock(self, symbol: str, upper_limit: Optional[float] = None, lower_limit: Optional[float] = None):
        symbol = symbol.upper().strip()
        if not symbol:
            return False
        
        self.stocks[symbol] = StockThreshold(
            symbol=symbol,
            upper_limit=upper_limit,
            lower_limit=lower_limit
        )
        self.save_config()
        return True
    
    def remove_stock(self, symbol: str):
        symbol = symbol.upper().strip()
        if symbol in self.stocks:
            del self.stocks[symbol]
            self.save_config()
            return True
        return False
    
    def update_thresholds(self, symbol: str, upper_limit: Optional[float] = None, lower_limit: Optional[float] = None):
        symbol = symbol.upper().strip()
        if symbol not in self.stocks:
            return False
        
        if upper_limit is not None:
            self.stocks[symbol].upper_limit = upper_limit
        if lower_limit is not None:
            self.stocks[symbol].lower_limit = lower_limit
        
        self.save_config()
        return True
    
    def get_stock_price(self, symbol: str) -> Optional[float]:
        try:
            url = f"{self.base_url}?symbol={symbol}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'priceInfo' in data and 'lastPrice' in data['priceInfo']:
                    return float(data['priceInfo']['lastPrice'])
            elif response.status_code == 404:
                logger.warning(f"Stock {symbol} not found on NSE")
            else:
                logger.error(f"Error fetching data for {symbol}: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
        
        return None
    
    def check_alerts(self, symbol: str, current_price: float):
        if symbol not in self.stocks:
            return None
        
        threshold = self.stocks[symbol]
        alert = None
        
        # Check upper threshold
        if threshold.upper_limit is not None:
            if current_price > threshold.upper_limit and not threshold.last_alert_upper:
                alert = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'threshold': threshold.upper_limit,
                    'type': 'UPPER',
                    'message': f'{symbol} crossed UPPER threshold'
                }
                threshold.last_alert_upper = True
            elif current_price <= threshold.upper_limit:
                threshold.last_alert_upper = False
        
        # Check lower threshold
        if threshold.lower_limit is not None:
            if current_price < threshold.lower_limit and not threshold.last_alert_lower:
                alert = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'threshold': threshold.lower_limit,
                    'type': 'LOWER',
                    'message': f'{symbol} crossed LOWER threshold'
                }
                threshold.last_alert_lower = True
            elif current_price >= threshold.lower_limit:
                threshold.last_alert_lower = False
        
        return alert
    
    def get_all_prices(self) -> Dict[str, float]:
        prices = {}
        for symbol in list(self.stocks.keys()):
            price = self.get_stock_price(symbol)
            if price:
                prices[symbol] = price
        return prices
    
    def is_market_hours(self):
        now = datetime.now()
        
        # Weekend check
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Market hours: 9:15 AM to 3:30 PM
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close

# Initialize the monitor
monitor = NSEStockMonitor()

# Background monitoring thread
def background_monitoring():
    while monitor.monitoring_active:
        if monitor.is_market_hours():
            prices = monitor.get_all_prices()
            
            for symbol, price in prices.items():
                alert = monitor.check_alerts(symbol, price)
                if alert:
                    socketio.emit('alert', alert)
                    logger.info(f"Alert triggered: {alert}")
            
            # Emit current prices
            socketio.emit('price_update', prices)
        
        time.sleep(60)  # Check every minute

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stocks')
def get_stocks():
    stocks_data = {}
    prices = monitor.get_all_prices()
    
    for symbol, threshold in monitor.stocks.items():
        stocks_data[symbol] = {
            'symbol': threshold.symbol,
            'upper_limit': threshold.upper_limit,
            'lower_limit': threshold.lower_limit,
            'current_price': prices.get(symbol, None),
            'price_change': None  # Could be calculated based on historical data
        }
    
    return jsonify(stocks_data)

@app.route('/api/stocks', methods=['POST'])
def add_stock():
    data = request.json
    symbol = data.get('symbol', '').strip()
    upper_limit = data.get('upper_limit')
    lower_limit = data.get('lower_limit')
    
    if not symbol:
        return jsonify({'error': 'Symbol is required'}), 400
    
    # Validate thresholds
    if upper_limit is not None:
        try:
            upper_limit = float(upper_limit)
            if upper_limit <= 0:
                return jsonify({'error': 'Upper limit must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid upper limit'}), 400
    
    if lower_limit is not None:
        try:
            lower_limit = float(lower_limit)
            if lower_limit <= 0:
                return jsonify({'error': 'Lower limit must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid lower limit'}), 400
    
    if upper_limit and lower_limit and upper_limit <= lower_limit:
        return jsonify({'error': 'Upper limit must be greater than lower limit'}), 400
    
    success = monitor.add_stock(symbol, upper_limit, lower_limit)
    if success:
        return jsonify({'message': f'Stock {symbol} added successfully'})
    else:
        return jsonify({'error': 'Failed to add stock'}), 500

@app.route('/api/stocks/<symbol>', methods=['DELETE'])
def remove_stock(symbol):
    success = monitor.remove_stock(symbol)
    if success:
        return jsonify({'message': f'Stock {symbol} removed successfully'})
    else:
        return jsonify({'error': 'Stock not found'}), 404

@app.route('/api/stocks/<symbol>', methods=['PUT'])
def update_stock(symbol):
    data = request.json
    upper_limit = data.get('upper_limit')
    lower_limit = data.get('lower_limit')
    
    # Validate thresholds
    if upper_limit is not None:
        try:
            upper_limit = float(upper_limit)
            if upper_limit <= 0:
                return jsonify({'error': 'Upper limit must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid upper limit'}), 400
    
    if lower_limit is not None:
        try:
            lower_limit = float(lower_limit)
            if lower_limit <= 0:
                return jsonify({'error': 'Lower limit must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid lower limit'}), 400
    
    if upper_limit and lower_limit and upper_limit <= lower_limit:
        return jsonify({'error': 'Upper limit must be greater than lower limit'}), 400
    
    success = monitor.update_thresholds(symbol, upper_limit, lower_limit)
    if success:
        return jsonify({'message': f'Stock {symbol} updated successfully'})
    else:
        return jsonify({'error': 'Stock not found'}), 404

@app.route('/api/monitoring/start', methods=['POST'])
def start_monitoring():
    if not monitor.monitoring_active:
        monitor.monitoring_active = True
        monitor.monitoring_thread = threading.Thread(target=background_monitoring)
        monitor.monitoring_thread.daemon = True
        monitor.monitoring_thread.start()
        return jsonify({'message': 'Monitoring started'})
    else:
        return jsonify({'message': 'Monitoring already active'})

@app.route('/api/monitoring/stop', methods=['POST'])
def stop_monitoring():
    monitor.monitoring_active = False
    return jsonify({'message': 'Monitoring stopped'})

@app.route('/api/monitoring/status')
def monitoring_status():
    return jsonify({
        'active': monitor.monitoring_active,
        'market_hours': monitor.is_market_hours()
    })

@app.route('/api/alerts')
def get_alerts():
    # Read alerts from log file
    alerts = []
    log_file = "stock_alerts.log"
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-20:]:  # Last 20 lines
                    if 'ALERT' in line:
                        alerts.append(line.strip())
        except Exception as e:
            logger.error(f"Error reading alerts: {e}")
    
    return jsonify(alerts)

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    emit('connected', {'data': 'Connected to NSE Stock Monitor'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('refresh_prices')
def handle_refresh_prices():
    prices = monitor.get_all_prices()
    emit('price_update', prices)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_socketio import SocketIO, emit
import threading
import time
import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
import requests
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'b3c4f17552b399a339b71fef5c5af905')
socketio = SocketIO(app, cors_allowed_origins="*")

@dataclass
class StockThreshold:
    symbol: str
    upper_limit: Optional[float] = None
    lower_limit: Optional[float] = None
    last_alert_upper: bool = False
    last_alert_lower: bool = False

class NSEStockMonitor:
    def __init__(self, config_file: str = "stock_config.json"):
        self.config_file = config_file
        self.stocks: Dict[str, StockThreshold] = {}
        self.base_url = "https://www.nseindia.com/api/quote-equity"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.monitoring_active = False
        self.monitoring_thread = None
        self.load_config()
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    for symbol, data in config.items():
                        self.stocks[symbol] = StockThreshold(**data)
                logger.info(f"Loaded {len(self.stocks)} stocks from configuration")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self.stocks = {}
    
    def save_config(self):
        config = {}
        for symbol, threshold in self.stocks.items():
            config[symbol] = asdict(threshold)
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuration saved to {self.config_file}")
    
    def add_stock(self, symbol: str, upper_limit: Optional[float] = None, lower_limit: Optional[float] = None):
        symbol = symbol.upper().strip()
        if not symbol:
            return False
        
        self.stocks[symbol] = StockThreshold(
            symbol=symbol,
            upper_limit=upper_limit,
            lower_limit=lower_limit
        )
        self.save_config()
        return True
    
    def remove_stock(self, symbol: str):
        symbol = symbol.upper().strip()
        if symbol in self.stocks:
            del self.stocks[symbol]
            self.save_config()
            return True
        return False
    
    def update_thresholds(self, symbol: str, upper_limit: Optional[float] = None, lower_limit: Optional[float] = None):
        symbol = symbol.upper().strip()
        if symbol not in self.stocks:
            return False
        
        if upper_limit is not None:
            self.stocks[symbol].upper_limit = upper_limit
        if lower_limit is not None:
            self.stocks[symbol].lower_limit = lower_limit
        
        self.save_config()
        return True
    
    def get_stock_price(self, symbol: str) -> Optional[float]:
        try:
            url = f"{self.base_url}?symbol={symbol}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'priceInfo' in data and 'lastPrice' in data['priceInfo']:
                    return float(data['priceInfo']['lastPrice'])
            elif response.status_code == 404:
                logger.warning(f"Stock {symbol} not found on NSE")
            else:
                logger.error(f"Error fetching data for {symbol}: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
        
        return None
    
    def check_alerts(self, symbol: str, current_price: float):
        if symbol not in self.stocks:
            return None
        
        threshold = self.stocks[symbol]
        alert = None
        
        # Check upper threshold
        if threshold.upper_limit is not None:
            if current_price > threshold.upper_limit and not threshold.last_alert_upper:
                alert = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'threshold': threshold.upper_limit,
                    'type': 'UPPER',
                    'message': f'{symbol} crossed UPPER threshold'
                }
                threshold.last_alert_upper = True
            elif current_price <= threshold.upper_limit:
                threshold.last_alert_upper = False
        
        # Check lower threshold
        if threshold.lower_limit is not None:
            if current_price < threshold.lower_limit and not threshold.last_alert_lower:
                alert = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'threshold': threshold.lower_limit,
                    'type': 'LOWER',
                    'message': f'{symbol} crossed LOWER threshold'
                }
                threshold.last_alert_lower = True
            elif current_price >= threshold.lower_limit:
                threshold.last_alert_lower = False
        
        return alert
    
    def get_all_prices(self) -> Dict[str, float]:
        prices = {}
        for symbol in list(self.stocks.keys()):
            price = self.get_stock_price(symbol)
            if price:
                prices[symbol] = price
        return prices
    
    def is_market_hours(self):
        now = datetime.now()
        
        # Weekend check
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Market hours: 9:15 AM to 3:30 PM
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close

# Initialize the monitor
monitor = NSEStockMonitor()

# Background monitoring thread
def background_monitoring():
    while monitor.monitoring_active:
        if monitor.is_market_hours():
            prices = monitor.get_all_prices()
            
            for symbol, price in prices.items():
                alert = monitor.check_alerts(symbol, price)
                if alert:
                    socketio.emit('alert', alert)
                    logger.info(f"Alert triggered: {alert}")
            
            # Emit current prices
            socketio.emit('price_update', prices)
        
        time.sleep(60)  # Check every minute

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stocks')
def get_stocks():
    stocks_data = {}
    prices = monitor.get_all_prices()
    
    for symbol, threshold in monitor.stocks.items():
        stocks_data[symbol] = {
            'symbol': threshold.symbol,
            'upper_limit': threshold.upper_limit,
            'lower_limit': threshold.lower_limit,
            'current_price': prices.get(symbol, None),
            'price_change': None  # Could be calculated based on historical data
        }
    
    return jsonify(stocks_data)

@app.route('/api/stocks', methods=['POST'])
def add_stock():
    data = request.json
    symbol = data.get('symbol', '').strip()
    upper_limit = data.get('upper_limit')
    lower_limit = data.get('lower_limit')
    
    if not symbol:
        return jsonify({'error': 'Symbol is required'}), 400
    
    # Validate thresholds
    if upper_limit is not None:
        try:
            upper_limit = float(upper_limit)
            if upper_limit <= 0:
                return jsonify({'error': 'Upper limit must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid upper limit'}), 400
    
    if lower_limit is not None:
        try:
            lower_limit = float(lower_limit)
            if lower_limit <= 0:
                return jsonify({'error': 'Lower limit must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid lower limit'}), 400
    
    if upper_limit and lower_limit and upper_limit <= lower_limit:
        return jsonify({'error': 'Upper limit must be greater than lower limit'}), 400
    
    success = monitor.add_stock(symbol, upper_limit, lower_limit)
    if success:
        return jsonify({'message': f'Stock {symbol} added successfully'})
    else:
        return jsonify({'error': 'Failed to add stock'}), 500

@app.route('/api/stocks/<symbol>', methods=['DELETE'])
def remove_stock(symbol):
    success = monitor.remove_stock(symbol)
    if success:
        return jsonify({'message': f'Stock {symbol} removed successfully'})
    else:
        return jsonify({'error': 'Stock not found'}), 404

@app.route('/api/stocks/<symbol>', methods=['PUT'])
def update_stock(symbol):
    data = request.json
    upper_limit = data.get('upper_limit')
    lower_limit = data.get('lower_limit')
    
    # Validate thresholds
    if upper_limit is not None:
        try:
            upper_limit = float(upper_limit)
            if upper_limit <= 0:
                return jsonify({'error': 'Upper limit must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid upper limit'}), 400
    
    if lower_limit is not None:
        try:
            lower_limit = float(lower_limit)
            if lower_limit <= 0:
                return jsonify({'error': 'Lower limit must be positive'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid lower limit'}), 400
    
    if upper_limit and lower_limit and upper_limit <= lower_limit:
        return jsonify({'error': 'Upper limit must be greater than lower limit'}), 400
    
    success = monitor.update_thresholds(symbol, upper_limit, lower_limit)
    if success:
        return jsonify({'message': f'Stock {symbol} updated successfully'})
    else:
        return jsonify({'error': 'Stock not found'}), 404

@app.route('/api/monitoring/start', methods=['POST'])
def start_monitoring():
    if not monitor.monitoring_active:
        monitor.monitoring_active = True
        monitor.monitoring_thread = threading.Thread(target=background_monitoring)
        monitor.monitoring_thread.daemon = True
        monitor.monitoring_thread.start()
        return jsonify({'message': 'Monitoring started'})
    else:
        return jsonify({'message': 'Monitoring already active'})

@app.route('/api/monitoring/stop', methods=['POST'])
def stop_monitoring():
    monitor.monitoring_active = False
    return jsonify({'message': 'Monitoring stopped'})

@app.route('/api/monitoring/status')
def monitoring_status():
    return jsonify({
        'active': monitor.monitoring_active,
        'market_hours': monitor.is_market_hours()
    })

@app.route('/api/alerts')
def get_alerts():
    # Read alerts from log file
    alerts = []
    log_file = "stock_alerts.log"
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-20:]:  # Last 20 lines
                    if 'ALERT' in line:
                        alerts.append(line.strip())
        except Exception as e:
            logger.error(f"Error reading alerts: {e}")
    
    return jsonify(alerts)

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    emit('connected', {'data': 'Connected to NSE Stock Monitor'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('refresh_prices')
def handle_refresh_prices():
    prices = monitor.get_all_prices()
    emit('price_update', prices)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
