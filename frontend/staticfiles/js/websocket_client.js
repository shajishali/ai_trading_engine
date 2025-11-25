/**
 * WebSocket Client for Django Channels
 * Manages real-time connections for market data, trading signals, and notifications
 */

class WebSocketClient {
    constructor() {
        this.connections = {
            marketData: null,
            tradingSignals: null,
            notifications: null
        };
        this.reconnectAttempts = {};
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.isConnected = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.initializeConnections();
    }
    
    setupEventListeners() {
        // Connection status indicators
        document.addEventListener('DOMContentLoaded', () => {
            this.updateConnectionStatus();
        });
        
        // Manual connection controls
        const connectButtons = document.querySelectorAll('[data-websocket-connect]');
        connectButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const type = button.dataset.websocketConnect;
                this.connect(type);
            });
        });
        
        // Manual disconnection controls
        const disconnectButtons = document.querySelectorAll('[data-websocket-disconnect]');
        disconnectButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const type = button.dataset.websocketDisconnect;
                this.disconnect(type);
            });
        });
    }
    
    initializeConnections() {
        // Initialize all WebSocket connections
        this.connect('marketData');
        this.connect('tradingSignals');
        this.connect('notifications');
    }
    
    connect(type) {
        if (this.connections[type] && this.connections[type].readyState === WebSocket.OPEN) {
            console.log(`${type} WebSocket already connected`);
            return;
        }
        
        const wsUrl = this.getWebSocketUrl(type);
        if (!wsUrl) {
            console.error(`No WebSocket URL configured for ${type}`);
            return;
        }
        
        try {
            this.connections[type] = new WebSocket(wsUrl);
            this.setupConnectionHandlers(type);
            console.log(`Connecting to ${type} WebSocket...`);
        } catch (error) {
            console.error(`Error creating ${type} WebSocket:`, error);
        }
    }
    
    getWebSocketUrl(type) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        
        switch (type) {
            case 'marketData':
                return `${protocol}//${host}/ws/market-data/`;
            case 'tradingSignals':
                return `${protocol}//${host}/ws/trading-signals/`;
            case 'notifications':
                return `${protocol}//${host}/ws/notifications/`;
            default:
                return null;
        }
    }
    
    setupConnectionHandlers(type) {
        const ws = this.connections[type];
        
        ws.onopen = (event) => {
            console.log(`${type} WebSocket connected`);
            this.isConnected = true;
            this.reconnectAttempts[type] = 0;
            this.updateConnectionStatus();
            this.onConnectionEstablished(type);
        };
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(type, data);
            } catch (error) {
                console.error(`Error parsing ${type} WebSocket message:`, error);
            }
        };
        
        ws.onclose = (event) => {
            console.log(`${type} WebSocket disconnected:`, event.code, event.reason);
            this.isConnected = false;
            this.updateConnectionStatus();
            this.onConnectionClosed(type, event);
            
            // Attempt to reconnect if not manually closed
            if (event.code !== 1000) {
                this.scheduleReconnect(type);
            }
        };
        
        ws.onerror = (error) => {
            console.error(`${type} WebSocket error:`, error);
            this.onConnectionError(type, error);
        };
    }
    
    handleMessage(type, data) {
        switch (data.type) {
            case 'connection_established':
                console.log(`${type} connection established:`, data.message);
                break;
                
            case 'market_update':
                this.handleMarketUpdate(data);
                break;
                
            case 'new_signal':
                this.handleNewSignal(data);
                break;
                
            case 'new_notification':
                this.handleNewNotification(data);
                break;
                
            case 'portfolio_update':
                this.handlePortfolioUpdate(data);
                break;
                
            case 'price_alert':
                this.handlePriceAlert(data);
                break;
                
            case 'error':
                console.error(`${type} WebSocket error:`, data.message);
                break;
                
            default:
                console.log(`Unknown ${type} message type:`, data.type);
        }
    }
    
    handleMarketUpdate(data) {
        // Update market data display
        const marketDataElement = document.querySelector(`[data-market-data="${data.symbol}"]`);
        if (marketDataElement) {
            marketDataElement.innerHTML = `
                <div class="market-update">
                    <span class="symbol">${data.symbol}</span>
                    <span class="price">$${data.price}</span>
                    <span class="change ${data.change >= 0 ? 'positive' : 'negative'}">
                        ${data.change >= 0 ? '+' : ''}${data.change}%
                    </span>
                    <span class="volume">Vol: ${data.volume}</span>
                    <span class="timestamp">${new Date(data.timestamp).toLocaleTimeString()}</span>
                </div>
            `;
        }
        
        // Trigger custom event for other components
        const event = new CustomEvent('marketUpdate', { detail: data });
        document.dispatchEvent(event);
    }
    
    handleNewSignal(data) {
        // Update trading signals display
        const signalsContainer = document.querySelector('[data-trading-signals]');
        if (signalsContainer) {
            const signalElement = document.createElement('div');
            signalElement.className = 'trading-signal new-signal';
            signalElement.innerHTML = `
                <div class="signal-header">
                    <span class="symbol">${data.symbol}</span>
                    <span class="signal-type ${data.signal_type}">${data.signal_type}</span>
                    <span class="strength">Strength: ${data.strength}</span>
                </div>
                <div class="signal-details">
                    <span class="entry-price">Entry: $${data.entry_price}</span>
                    <span class="target-price">Target: $${data.target_price}</span>
                    <span class="stop-loss">Stop: $${data.stop_loss}</span>
                </div>
                <div class="signal-confidence">
                    Confidence: ${data.confidence_score}%
                </div>
                <div class="signal-timestamp">
                    ${new Date(data.timestamp).toLocaleString()}
                </div>
            `;
            
            signalsContainer.insertBefore(signalElement, signalsContainer.firstChild);
            
            // Remove old signals if too many
            const signals = signalsContainer.querySelectorAll('.trading-signal');
            if (signals.length > 10) {
                signals[signals.length - 1].remove();
            }
        }
        
        // Trigger custom event
        const event = new CustomEvent('newTradingSignal', { detail: data });
        document.dispatchEvent(event);
    }
    
    handleNewNotification(data) {
        // Create notification toast
        this.showNotificationToast(data);
        
        // Update notifications count
        this.updateNotificationCount();
        
        // Trigger custom event
        const event = new CustomEvent('newNotification', { detail: data });
        document.dispatchEvent(event);
    }
    
    handlePortfolioUpdate(data) {
        // Update portfolio display
        const portfolioElements = document.querySelectorAll('[data-portfolio-update]');
        portfolioElements.forEach(element => {
            if (element.dataset.portfolioUpdate === 'total-value') {
                element.textContent = `$${data.total_value.toLocaleString()}`;
            } else if (element.dataset.portfolioUpdate === 'daily-change') {
                element.textContent = `${data.daily_change >= 0 ? '+' : ''}$${data.daily_change.toLocaleString()}`;
                element.className = data.daily_change >= 0 ? 'positive' : 'negative';
            } else if (element.dataset.portfolioUpdate === 'daily-change-percent') {
                element.textContent = `${data.daily_change_percent >= 0 ? '+' : ''}${data.daily_change_percent}%`;
                element.className = data.daily_change_percent >= 0 ? 'positive' : 'negative';
            }
        });
        
        // Trigger custom event
        const event = new CustomEvent('portfolioUpdate', { detail: data });
        document.dispatchEvent(event);
    }
    
    handlePriceAlert(data) {
        // Show price alert notification
        this.showPriceAlert(data);
        
        // Trigger custom event
        const event = new CustomEvent('priceAlert', { detail: data });
        document.dispatchEvent(event);
    }
    
    showNotificationToast(notification) {
        const toast = document.createElement('div');
        toast.className = `notification-toast ${notification.notification_type}`;
        toast.innerHTML = `
            <div class="toast-header">
                <span class="title">${notification.title}</span>
                <button class="close-btn" onclick="this.parentElement.parentElement.remove()">&times;</button>
            </div>
            <div class="toast-body">
                ${notification.message}
            </div>
            <div class="toast-footer">
                <span class="priority ${notification.priority}">${notification.priority}</span>
                <span class="timestamp">${new Date(notification.timestamp).toLocaleTimeString()}</span>
            </div>
        `;
        
        // Add to notifications container
        const container = document.querySelector('.notifications-container') || document.body;
        container.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    }
    
    showPriceAlert(alert) {
        const alertElement = document.createElement('div');
        alertElement.className = `price-alert ${alert.alert_type}`;
        alertElement.innerHTML = `
            <div class="alert-content">
                <span class="symbol">${alert.symbol}</span>
                <span class="message">${alert.message}</span>
                <span class="price">$${alert.price}</span>
                <span class="timestamp">${new Date(alert.timestamp).toLocaleTimeString()}</span>
            </div>
        `;
        
        // Add to alerts container
        const container = document.querySelector('.price-alerts-container') || document.body;
        container.appendChild(alertElement);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (alertElement.parentElement) {
                alertElement.remove();
            }
        }, 10000);
    }
    
    updateNotificationCount() {
        const countElement = document.querySelector('[data-notification-count]');
        if (countElement) {
            const currentCount = parseInt(countElement.textContent) || 0;
            countElement.textContent = currentCount + 1;
        }
    }
    
    disconnect(type) {
        if (this.connections[type]) {
            this.connections[type].close(1000, 'Manual disconnect');
            this.connections[type] = null;
            console.log(`${type} WebSocket disconnected manually`);
        }
    }
    
    disconnectAll() {
        Object.keys(this.connections).forEach(type => {
            this.disconnect(type);
        });
    }
    
    scheduleReconnect(type) {
        if (this.reconnectAttempts[type] >= this.maxReconnectAttempts) {
            console.error(`Max reconnection attempts reached for ${type}`);
            return;
        }
        
        this.reconnectAttempts[type] = (this.reconnectAttempts[type] || 0) + 1;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts[type] - 1);
        
        console.log(`Scheduling ${type} reconnection in ${delay}ms (attempt ${this.reconnectAttempts[type]})`);
        
        setTimeout(() => {
            this.connect(type);
        }, delay);
    }
    
    updateConnectionStatus() {
        Object.keys(this.connections).forEach(type => {
            const statusElement = document.querySelector(`[data-connection-status="${type}"]`);
            if (statusElement) {
                const isConnected = this.connections[type] && 
                                  this.connections[type].readyState === WebSocket.OPEN;
                
                statusElement.textContent = isConnected ? 'Connected' : 'Disconnected';
                statusElement.className = isConnected ? 'status-connected' : 'status-disconnected';
            }
        });
    }
    
    onConnectionEstablished(type) {
        // Send initial subscription messages
        if (type === 'marketData') {
            this.sendMessage(type, {
                type: 'subscribe_symbol',
                symbol: 'BTC-USD'
            });
        } else if (type === 'tradingSignals') {
            this.sendMessage(type, {
                type: 'subscribe_signals'
            });
        }
    }
    
    onConnectionClosed(type, event) {
        // Handle connection closure
        console.log(`${type} connection closed:`, event.code, event.reason);
    }
    
    onConnectionError(type, error) {
        // Handle connection errors
        console.error(`${type} connection error:`, error);
    }
    
    sendMessage(type, data) {
        if (this.connections[type] && this.connections[type].readyState === WebSocket.OPEN) {
            this.connections[type].send(JSON.stringify(data));
        } else {
            console.error(`Cannot send message to ${type}: WebSocket not connected`);
        }
    }
    
    // Public methods for external use
    subscribeToSymbol(symbol) {
        this.sendMessage('marketData', {
            type: 'subscribe_symbol',
            symbol: symbol
        });
    }
    
    unsubscribeFromSymbol(symbol) {
        this.sendMessage('marketData', {
            type: 'unsubscribe_symbol',
            symbol: symbol
        });
    }
    
    filterSignals(symbol, signalType) {
        this.sendMessage('tradingSignals', {
            type: 'filter_signals',
            symbol: symbol,
            signal_type: signalType
        });
    }
    
    markNotificationRead(notificationId) {
        this.sendMessage('notifications', {
            type: 'mark_read',
            notification_id: notificationId
        });
    }
}

// Initialize WebSocket client when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.websocketClient = new WebSocketClient();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketClient;
}









