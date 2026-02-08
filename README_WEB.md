# NSE Stock Monitor - Web Application

A modern web application for monitoring NSE (National Stock Exchange of India) stock prices in real-time with customizable price alerts.

## Features

- **Real-time Price Monitoring**: Live stock price updates via WebSocket connections
- **Interactive Web Interface**: Modern, responsive dashboard with Bootstrap 5
- **Customizable Alerts**: Set upper and lower price thresholds with instant notifications
- **Browser Notifications**: Desktop alerts when stocks cross your thresholds
- **Market Hours Awareness**: Automatically monitors only during NSE trading hours
- **Live Data Updates**: Real-time price updates without page refresh
- **Stock Management**: Add, edit, or remove stocks with an intuitive interface
- **Alert History**: View recent alerts and monitoring statistics
- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile devices

## Installation

1. **Install Python 3.7 or higher**

2. **Install required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the web application:**
   ```bash
   python app.py
   ```

4. **Open your browser and navigate to:**
   ```
   http://localhost:5000
   ```

## Web Application Features

### Dashboard Overview
- **Stock Table**: View all monitored stocks with current prices and thresholds
- **Control Panel**: Start/stop monitoring, refresh prices, add new stocks
- **Alert Panel**: Real-time alerts displayed as they occur
- **Statistics**: Total stocks, alerts count, and last update time

### Stock Management
- **Add Stocks**: Enter symbol and set upper/lower thresholds
- **Edit Thresholds**: Modify price limits for existing stocks
- **Remove Stocks**: Remove stocks from monitoring list
- **Real-time Updates**: Prices update automatically every 30 seconds

### Alert System
- **Visual Alerts**: Color-coded alerts in the dashboard
- **Browser Notifications**: Desktop notifications for price crossings
- **Alert History**: Recent alerts displayed in the sidebar
- **Alert Types**: 
  - 🔴 Upper threshold crossed
  - 🟡 Lower threshold crossed

### Monitoring Controls
- **Start/Stop**: Control monitoring with a single click
- **Market Status**: Shows whether market is open/closed
- **Connection Status**: WebSocket connection indicator
- **Refresh**: Manual price refresh option

## API Endpoints

The application provides RESTful APIs for integration:

### Stock Management
- `GET /api/stocks` - Get all monitored stocks
- `POST /api/stocks` - Add a new stock
- `PUT /api/stocks/<symbol>` - Update stock thresholds
- `DELETE /api/stocks/<symbol>` - Remove a stock

### Monitoring
- `POST /api/monitoring/start` - Start monitoring
- `POST /api/monitoring/stop` - Stop monitoring
- `GET /api/monitoring/status` - Get monitoring status

### Alerts
- `GET /api/alerts` - Get recent alerts

## WebSocket Events

Real-time communication via Socket.IO:

### Client → Server
- `refresh_prices` - Request immediate price update

### Server → Client
- `price_update` - Real-time price updates
- `alert` - Price threshold alerts
- `connected` - Connection confirmation

## Usage Examples

### Adding a Stock via Web Interface
1. Enter stock symbol (e.g., "RELIANCE")
2. Set upper limit (e.g., 2500)
3. Set lower limit (e.g., 2400)
4. Click "Add Stock"

### Monitoring Workflow
1. Add stocks with price thresholds
2. Click "Start Monitoring"
3. Monitor real-time price updates
4. Receive instant alerts for threshold crossings
5. Adjust thresholds as needed

## Browser Notifications

Enable desktop notifications for instant alerts:
- Grant permission when prompted
- Receive alerts even when browser is minimized
- Click notifications to return to the dashboard

## Configuration

Stock settings are automatically saved to `stock_config.json`:
```json
{
  "RELIANCE": {
    "symbol": "RELIANCE",
    "upper_limit": 2500.0,
    "lower_limit": 2400.0,
    "last_alert_upper": false,
    "last_alert_lower": false
  }
}
```

## Market Hours

The application automatically respects NSE trading hours:
- **Monday-Friday**: 9:15 AM - 3:30 PM
- **Weekends**: No monitoring
- **Status Display**: Shows market status in real-time

## Troubleshooting

### Common Issues

**WebSocket Connection Issues:**
- Check if port 5000 is available
- Verify firewall settings
- Refresh the browser page

**Price Fetching Errors:**
- Verify stock symbols are correct (NSE format)
- Check internet connection
- NSE API may have rate limits

**Browser Notifications Not Working:**
- Grant notification permissions
- Check browser settings
- Ensure browser supports notifications

### Performance Tips

- Monitor a reasonable number of stocks (< 50)
- Set appropriate refresh intervals
- Clear alert history periodically
- Use modern browsers for best performance

## Security Considerations

- Change the secret key in production
- Use HTTPS in production environments
- Implement user authentication for multi-user access
- Rate limit API endpoints
- Validate all user inputs

## Production Deployment

### Using Gunicorn
```bash
pip install gunicorn eventlet
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
```

### Using Docker
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

### Environment Variables
- `FLASK_ENV=production` - Production mode
- `SECRET_KEY=your-secret-key` - Change the default secret

## Browser Compatibility

- Chrome 60+
- Firefox 55+
- Safari 11+
- Edge 79+

## Mobile Features

- Responsive design for all screen sizes
- Touch-friendly controls
- Optimized performance for mobile devices
- Support for mobile browser notifications

## Extension Ideas

- User authentication and profiles
- Historical price charts
- Advanced alert conditions
- Email/SMS notifications
- Portfolio performance tracking
- Technical indicators
- Multiple exchange support

## Support

For issues and feature requests, please check the application logs and ensure all dependencies are properly installed.