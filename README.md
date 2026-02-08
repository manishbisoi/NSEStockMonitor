# NSE Stock Price Monitor

A Python program that monitors NSE (National Stock Exchange of India) stock prices in real-time and sends alerts when prices cross predefined thresholds.

## Features

- **Real-time Price Fetching**: Fetches current stock prices from NSE
- **Threshold Monitoring**: Set upper and lower price limits for each stock
- **Smart Alerts**: Get notified when stocks cross your thresholds
- **Market Hours Monitoring**: Automatically checks only during market hours (9:15 AM - 3:30 PM, Monday-Friday)
- **Modular Configuration**: Easily add/remove stocks and update thresholds
- **Interactive Mode**: User-friendly command-line interface
- **Persistent Storage**: Saves your configuration across sessions

## Installation

1. Install Python 3.7 or higher
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Interactive Mode (Recommended)
Run the program without arguments to use the interactive interface:
```bash
python nse_stock_monitor.py
```

### Command Line Interface

**Add a stock:**
```bash
python nse_stock_monitor.py --add RELIANCE --upper 2500 --lower 2400
```

**Remove a stock:**
```bash
python nse_stock_monitor.py --remove RELIANCE
```

**Update thresholds:**
```bash
python nse_stock_monitor.py --update RELIANCE --upper 2600 --lower 2300
```

**Start monitoring:**
```bash
python nse_stock_monitor.py --monitor --interval 5
```

**Show current status:**
```bash
python nse_stock_monitor.py --status
```

### Configuration File

The program uses `stock_config.json` to store your stock list and thresholds. You can edit this file directly:

```json
{
  "RELIANCE": {
    "symbol": "RELIANCE",
    "upper_limit": 2500.0,
    "lower_limit": 2400.0,
    "last_alert_upper": false,
    "last_alert_lower": false
  },
  "TCS": {
    "symbol": "TCS",
    "upper_limit": 3700.0,
    "lower_limit": 3500.0,
    "last_alert_upper": false,
    "last_alert_lower": false
  }
}
```

## Alert Examples

When a stock crosses your threshold, you'll see alerts like:

```
==================================================
🔺 ALERT: RELIANCE crossed UPPER threshold

Stock Symbol: RELIANCE
Current Price: ₹2523.45
Threshold: ₹2500.00
Time: 2024-02-05 14:30:15
Price is above the set threshold!
==================================================
```

## Features in Detail

### Market Hours
- Only monitors during NSE market hours (9:15 AM to 3:30 PM)
- Automatically skips weekends
- Shows current prices during market hours only

### Smart Alerting
- Only sends alerts once per threshold crossing
- Resets when price goes back within thresholds
- Logs all alerts to `stock_alerts.log`

### Error Handling
- Gracefully handles network issues
- Continues monitoring other stocks if one fails
- Shows clear error messages

## Common Stock Symbols

- RELIANCE - Reliance Industries
- TCS - Tata Consultancy Services
- INFY - Infosys
- HDFCBANK - HDFC Bank
- ICICIBANK - ICICI Bank
- HINDUNILVR - Hindustan Unilever
- SBIN - State Bank of India
- BHARTIARTL - Bharti Airtel

## Troubleshooting

**Issue: "Stock not found on NSE"**
- Ensure the stock symbol is correct (use NSE format, not BSE)
- Check if the stock is actively traded

**Issue: Network errors**
- Check your internet connection
- NSE APIs may have rate limits
- Try increasing the monitoring interval

**Issue: No alerts**
- Verify your thresholds are reasonable
- Check that market hours are active
- Review the alert log file

## Customization

You can extend the program by:
- Adding email/SMS notifications in the `send_alert` method
- Integrating with trading platforms
- Adding technical indicators
- Implementing different alert strategies

## License

This program is for educational purposes. Use at your own risk for real trading decisions.