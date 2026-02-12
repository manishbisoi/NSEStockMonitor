import requests
import json
import time
import random
import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import schedule
import threading
import sys
import os
from pathlib import Path


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
        # NSE blocks many automated clients. We'll prime the session with
        # a visit to the homepage to obtain required cookies and headers.
        self._primed = False
        self.load_config()

    def _prime_session(self, force: bool = False):
        """Hit the NSE homepage once to obtain cookies and mimic a browser.

        Call this before calling API endpoints. Setting force=True re-primes.
        """
        if self._primed and not force:
            return

        try:
            homepage = "https://www.nseindia.com"
            # use a short timeout so the app doesn't hang on startup
            resp = self.session.get(homepage, timeout=5)
            # Update Referer to homepage for subsequent API calls
            self.session.headers.update({'Referer': homepage})
            # mark primed if we got any response (200/301/302/403 etc.)
            self._primed = True
            # small sleep to mimic browser behaviour
            time.sleep(random.uniform(0.2, 0.6))
        except Exception:
            # don't raise - we'll retry when making the API call
            self._primed = False
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    for symbol, data in config.items():
                        self.stocks[symbol] = StockThreshold(**data)
                print(f"Loaded {len(self.stocks)} stocks from configuration")
            except Exception as e:
                print(f"Error loading config: {e}")
                self.stocks = {}
    
    def save_config(self):
        config = {}
        for symbol, threshold in self.stocks.items():
            config[symbol] = asdict(threshold)
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Configuration saved to {self.config_file}")
    
    def add_stock(self, symbol: str, upper_limit: Optional[float] = None, lower_limit: Optional[float] = None):
        symbol = symbol.upper().strip()
        if not symbol:
            print("Invalid stock symbol")
            return False
        
        self.stocks[symbol] = StockThreshold(
            symbol=symbol,
            upper_limit=upper_limit,
            lower_limit=lower_limit
        )
        self.save_config()
        print(f"Added {symbol} to monitoring")
        return True
    
    def remove_stock(self, symbol: str):
        symbol = symbol.upper().strip()
        if symbol in self.stocks:
            del self.stocks[symbol]
            self.save_config()
            print(f"Removed {symbol} from monitoring")
            return True
        else:
            print(f"{symbol} not found in monitoring list")
            return False
    
    def update_thresholds(self, symbol: str, upper_limit: Optional[float] = None, lower_limit: Optional[float] = None):
        symbol = symbol.upper().strip()
        if symbol not in self.stocks:
            print(f"{symbol} not found. Adding it first.")
            self.add_stock(symbol, upper_limit, lower_limit)
            return
        
        if upper_limit is not None:
            self.stocks[symbol].upper_limit = upper_limit
        if lower_limit is not None:
            self.stocks[symbol].lower_limit = lower_limit
        
        self.save_config()
        print(f"Updated thresholds for {symbol}")
    
    def get_stock_price(self, symbol: str) -> Optional[float]:
        try:
            # Ensure session is primed (cookies + headers)
            self._prime_session()

            url = f"{self.base_url}?symbol={symbol}"

            # retry loop with exponential backoff for transient 403/5xx
            for attempt in range(1, 4):
                response = self.session.get(url, timeout=10)

                if response.status_code == 200:
                    try:
                        data = response.json()
                        if 'priceInfo' in data and 'lastPrice' in data['priceInfo']:
                            # small throttle between requests
                            time.sleep(random.uniform(0.3, 1.0))
                            return float(data['priceInfo']['lastPrice'])
                    except ValueError:
                        print(f"Invalid JSON for {symbol}")
                        return None

                if response.status_code == 404:
                    print(f"Stock {symbol} not found on NSE")
                    return None

                if response.status_code == 403:
                    # server likely blocked our client/IP; re-prime cookies and retry
                    print(f"Received 403 for {symbol}, re-priming session (attempt {attempt})")
                    self._prime_session(force=True)
                else:
                    print(f"Error fetching data for {symbol}: HTTP {response.status_code}")

                # backoff before next attempt
                sleep_seconds = (2 ** attempt) * 0.5 + random.uniform(0, 0.5)
                time.sleep(sleep_seconds)
                
        except Exception as e:
            print(f"Error fetching price for {symbol}: {e}")
        
        return None
    
    def check_alerts(self, symbol: str, current_price: float):
        if symbol not in self.stocks:
            return
        
        threshold = self.stocks[symbol]
        
        # Check upper threshold
        if threshold.upper_limit is not None:
            if current_price > threshold.upper_limit and not threshold.last_alert_upper:
                self.send_alert(symbol, current_price, threshold.upper_limit, "UPPER")
                threshold.last_alert_upper = True
            elif current_price <= threshold.upper_limit:
                threshold.last_alert_upper = False
        
        # Check lower threshold
        if threshold.lower_limit is not None:
            if current_price < threshold.lower_limit and not threshold.last_alert_lower:
                self.send_alert(symbol, current_price, threshold.lower_limit, "LOWER")
                threshold.last_alert_lower = True
            elif current_price >= threshold.lower_limit:
                threshold.last_alert_lower = False
    
    def send_alert(self, symbol: str, current_price: float, threshold: float, alert_type: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if alert_type == "UPPER":
            message = f"🔺 ALERT: {symbol} crossed UPPER threshold"
            direction = "above"
        else:
            message = f"🔻 ALERT: {symbol} crossed LOWER threshold"
            direction = "below"
        
        alert_message = f"""
{message}
Stock Symbol: {symbol}
Current Price: ₹{current_price:.2f}
Threshold: ₹{threshold:.2f}
Time: {timestamp}
Price is {direction} the set threshold!
"""
        
        print("=" * 50)
        print(alert_message)
        print("=" * 50)
        
        # You can extend this to send emails, SMS, or push notifications
        self.log_alert(alert_message)
    
    def log_alert(self, message: str):
        log_file = "stock_alerts.log"
        with open(log_file, 'a') as f:
            f.write(f"\n{datetime.datetime.now()}: {message}\n")
    
    def monitor_stocks(self):
        if not self.stocks:
            print("No stocks configured for monitoring")
            return
        
        print(f"\nMonitoring {len(self.stocks)} stocks at {datetime.datetime.now().strftime('%H:%M:%S')}")
        
        for symbol in list(self.stocks.keys()):
            price = self.get_stock_price(symbol)
            if price:
                print(f"{symbol}: ₹{price:.2f}")
                self.check_alerts(symbol, price)
            else:
                print(f"{symbol}: Unable to fetch price")
    
    def is_market_hours(self):
        now = datetime.datetime.now()
        
        # Weekend check
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Market hours: 9:15 AM to 3:30 PM
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def start_monitoring(self, interval_minutes: int = 5):
        print(f"Starting NSE Stock Monitor (checking every {interval_minutes} minutes)")
        print("Press Ctrl+C to stop")
        
        def monitor_job():
            if self.is_market_hours():
                self.monitor_stocks()
            else:
                print(f"Market is closed. Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        schedule.every(interval_minutes).minutes.do(monitor_job)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
    
    def show_status(self):
        print("\n=== STOCK MONITORING STATUS ===")
        if not self.stocks:
            print("No stocks configured")
            return
        
        for symbol, threshold in self.stocks.items():
            price = self.get_stock_price(symbol)
            print(f"\nSymbol: {symbol}")
            print(f"Current Price: {'₹' + f'{price:.2f}' if price else 'N/A'}")
            print(f"Upper Limit: {'₹' + f'{threshold.upper_limit:.2f}' if threshold.upper_limit else 'Not set'}")
            print(f"Lower Limit: {'₹' + f'{threshold.lower_limit:.2f}' if threshold.lower_limit else 'Not set'}")
    
    def interactive_mode(self):
        print("=== NSE STOCK MONITOR - INTERACTIVE MODE ===")
        
        while True:
            print("\nOptions:")
            print("1. Add stock")
            print("2. Remove stock")
            print("3. Update thresholds")
            print("4. Show status")
            print("5. Start monitoring")
            print("6. Exit")
            
            try:
                choice = input("Enter your choice (1-6): ").strip()
                
                if choice == '1':
                    symbol = input("Enter stock symbol: ").strip()
                    upper = input("Enter upper limit (press Enter to skip): ").strip()
                    lower = input("Enter lower limit (press Enter to skip): ").strip()
                    
                    upper_limit = float(upper) if upper else None
                    lower_limit = float(lower) if lower else None
                    
                    self.add_stock(symbol, upper_limit, lower_limit)
                
                elif choice == '2':
                    symbol = input("Enter stock symbol to remove: ").strip()
                    self.remove_stock(symbol)
                
                elif choice == '3':
                    symbol = input("Enter stock symbol: ").strip()
                    upper = input("Enter new upper limit (press Enter to keep current): ").strip()
                    lower = input("Enter new lower limit (press Enter to keep current): ").strip()
                    
                    upper_limit = float(upper) if upper else None
                    lower_limit = float(lower) if lower else None
                    
                    self.update_thresholds(symbol, upper_limit, lower_limit)
                
                elif choice == '4':
                    self.show_status()
                
                elif choice == '5':
                    interval = input("Enter monitoring interval in minutes (default 5): ").strip()
                    interval_minutes = int(interval) if interval else 5
                    self.start_monitoring(interval_minutes)
                
                elif choice == '6':
                    print("Goodbye!")
                    break
                
                else:
                    print("Invalid choice. Please try again.")
            
            except ValueError:
                print("Invalid input. Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nExiting...")
                break


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='NSE Stock Price Monitor')
    parser.add_argument('--config', default='stock_config.json', help='Configuration file path')
    parser.add_argument('--add', help='Add stock symbol')
    parser.add_argument('--remove', help='Remove stock symbol')
    parser.add_argument('--update', help='Update thresholds for stock symbol')
    parser.add_argument('--upper', type=float, help='Upper threshold')
    parser.add_argument('--lower', type=float, help='Lower threshold')
    parser.add_argument('--monitor', action='store_true', help='Start monitoring')
    parser.add_argument('--interval', type=int, default=5, help='Monitoring interval in minutes')
    parser.add_argument('--status', action='store_true', help='Show current status')
    
    args = parser.parse_args()
    
    monitor = NSEStockMonitor(args.config)
    
    if args.add:
        monitor.add_stock(args.add, args.upper, args.lower)
    elif args.remove:
        monitor.remove_stock(args.remove)
    elif args.update:
        monitor.update_thresholds(args.update, args.upper, args.lower)
    elif args.status:
        monitor.show_status()
    elif args.monitor:
        monitor.start_monitoring(args.interval)
    else:
        monitor.interactive_mode()


if __name__ == "__main__":
    main()