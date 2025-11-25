/**
 * Real-Time Features JavaScript for Phase 6
 * Handles WebSocket connections, market data streaming, and notifications
 */

class RealTimeManager {
    constructor() {
        this.connections = {
            marketData: null,
            tradingSignals: null,
            notifications: null
        };
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.checkConnectionStatus();
    }
    
    setupEventListeners() {
        // Market data streaming controls
        const streamingControls = document.querySelectorAll('[data-streaming-action]');
        streamingControls.forEach(control => {
            control.addEventListener('click', (e) => {
                e.preventDefault();
                const action = control.dataset.streamingAction;
                const symbol = control.dataset.symbol;
                this.controlMarketDataStreaming(action, symbol);
            });
        });
        
        // Real-time connection controls
        const connectionControls = document.querySelectorAll('[data-connection-type]');
        connectionControls.forEach(control => {
            control.addEventListener('click', (e) => {
                e.preventDefault();
                const connectionType = control.dataset.connectionType;
                this.establishConnection(connectionType);
            });
        });
        
        // Notification controls
        const notificationControls = document.querySelectorAll('[data-notification-action]');
        notificationControls.forEach(control => {
            control.addEventListener('click', (e) => {
                e.preventDefault();
                const action = control.dataset.notificationAction;
                this.handleNotificationAction(action, control);
            });
        });
    }
    
    async checkConnectionStatus() {
        try {
            const response = await fetch('/core/api/realtime/status/');
            const data = await response.json();
            
            if (data.success) {
                this.updateConnectionStatus(data.connections);
                this.updateWebSocketUrls(data.websocket_urls);
            }
        } catch (error) {
            console.error('Error checking connection status:', error);
        }
    }
    
    updateConnectionStatus(connections) {
        Object.keys(connections).forEach(type => {
            const status = connections[type];
            const statusElement = document.querySelector(`[data-connection-status="${type}"]`);
            if (statusElement) {
                statusElement.textContent = status ? 'Connected' : 'Disconnected';
                statusElement.className = status ? 'status-connected' : 'status-disconnected';
            }
        });
    }
    
    updateWebSocketUrls(urls) {
        Object.keys(urls).forEach(type => {
            const url = urls[type];
            const urlElement = document.querySelector(`[data-websocket-url="${type}"]`);
            if (urlElement) {
                urlElement.textContent = url;
            }
        });
    }
    
    async establishConnection(connectionType) {
        try {
            const response = await fetch('/core/api/realtime/connect/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: `type=${connectionType}`
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.connectWebSocket(connectionType, data.websocket_url);
                this.showNotification('Success', data.message, 'success');
            } else {
                this.showNotification('Error', data.error, 'error');
            }
        } catch (error) {
            console.error('Error establishing connection:', error);
            this.showNotification('Error', 'Failed to establish connection', 'error');
        }
    }
    
    connectWebSocket(connectionType, url) {
        const wsUrl = `ws://${window.location.host}${url}`;
        
        try {
            const websocket = new WebSocket(wsUrl);
            
            websocket.onopen = () => {
                console.log(`${connectionType} WebSocket connected`);
                this.connections[connectionType] = websocket;
                this.updateConnectionStatus({ [connectionType]: true });
                this.showNotification('Connected', `${connectionType} connection established`, 'success');
            };
            
            websocket.onmessage = (event) => {
                this.handleWebSocketMessage(connectionType, event.data);
            };
            
            websocket.onclose = () => {
                console.log(`${connectionType} WebSocket disconnected`);
                this.connections[connectionType] = null;
                this.updateConnectionStatus({ [connectionType]: false });
                this.attemptReconnect(connectionType, url);
            };
            
            websocket.onerror = (error) => {
                console.error(`${connectionType} WebSocket error:`, error);
                this.showNotification('Error', `${connectionType} connection error`, 'error');
            };
            
        } catch (error) {
            console.error(`Error connecting to ${connectionType} WebSocket:`, error);
            this.showNotification('Error', `Failed to connect to ${connectionType}`, 'error');
        }
    }
    
    handleWebSocketMessage(connectionType, data) {
        try {
            const message = JSON.parse(data);
            
            switch (message.type) {
                case 'connection_established':
                    this.showNotification('Connected', message.message, 'success');
                    break;
                    
                case 'market_update':
                    this.updateMarketData(message);
                    break;
                    
                case 'price_alert':
                    this.showPriceAlert(message);
                    break;
                    
                case 'new_signal':
                    this.showNewSignal(message);
                    break;
                    
                case 'signal_update':
                    this.updateSignal(message);
                    break;
                    
                case 'new_notification':
                    this.showRealTimeNotification(message);
                    break;
                    
                case 'portfolio_update':
                    this.updatePortfolio(message);
                    break;
                    
                default:
                    console.log(`Unknown message type: ${message.type}`);
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    }
    
    updateMarketData(data) {
        // Update market data display
        const marketDataElement = document.querySelector(`[data-market-symbol="${data.symbol}"]`);
        if (marketDataElement) {
            const priceElement = marketDataElement.querySelector('.price');
            const changeElement = marketDataElement.querySelector('.change');
            const volumeElement = marketDataElement.querySelector('.volume');
            
            if (priceElement) priceElement.textContent = `$${data.price}`;
            if (changeElement) {
                changeElement.textContent = data.change >= 0 ? `+${data.change}` : data.change;
                changeElement.className = data.change >= 0 ? 'positive' : 'negative';
            }
            if (volumeElement) volumeElement.textContent = data.volume.toLocaleString();
        }
        
        // Update timestamp
        const timestampElement = document.querySelector(`[data-market-timestamp="${data.symbol}"]`);
        if (timestampElement) {
            timestampElement.textContent = new Date(data.timestamp).toLocaleTimeString();
        }
    }
    
    showPriceAlert(data) {
        this.showNotification(
            `Price Alert - ${data.symbol}`,
            data.message,
            'warning',
            'price-alert'
        );
        
        // Play alert sound if available
        this.playAlertSound();
    }
    
    showNewSignal(data) {
        this.showNotification(
            `New Trading Signal`,
            `${data.symbol}: ${data.signal_type} signal`,
            'info',
            'trading-signal'
        );
        
        // Update signals list if available
        this.updateSignalsList(data);
    }
    
    updateSignal(data) {
        // Update signal display
        const signalElement = document.querySelector(`[data-signal-id="${data.signal_id}"]`);
        if (signalElement) {
            const updateElement = signalElement.querySelector('.update-info');
            if (updateElement) {
                updateElement.textContent = `${data.update_type}: ${data.new_value}`;
                updateElement.className = 'update-info updated';
            }
        }
    }
    
    showRealTimeNotification(data) {
        this.showNotification(
            data.title,
            data.message,
            data.priority === 'high' ? 'error' : 'info',
            data.notification_type
        );
    }
    
    updatePortfolio(data) {
        // Update portfolio display
        const portfolioElement = document.querySelector('.portfolio-summary');
        if (portfolioElement) {
            const totalValueElement = portfolioElement.querySelector('.total-value');
            const dailyChangeElement = portfolioElement.querySelector('.daily-change');
            const dailyChangePercentElement = portfolioElement.querySelector('.daily-change-percent');
            
            if (totalValueElement) totalValueElement.textContent = `$${data.total_value.toLocaleString()}`;
            if (dailyChangeElement) {
                dailyChangeElement.textContent = data.daily_change >= 0 ? `+$${data.daily_change}` : `-$${Math.abs(data.daily_change)}`;
                dailyChangeElement.className = data.daily_change >= 0 ? 'positive' : 'negative';
            }
            if (dailyChangePercentElement) {
                dailyChangePercentElement.textContent = data.daily_change_percent >= 0 ? `+${data.daily_change_percent}%` : `${data.daily_change_percent}%`;
                dailyChangePercentElement.className = data.daily_change_percent >= 0 ? 'positive' : 'negative';
            }
        }
    }
    
    async controlMarketDataStreaming(action, symbol) {
        try {
            const response = await fetch('/core/api/realtime/streaming/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: `action=${action}&symbol=${symbol}`
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification('Success', data.message, 'success');
                this.updateStreamingStatus(symbol, action === 'start');
            } else {
                this.showNotification('Error', data.error, 'error');
            }
        } catch (error) {
            console.error('Error controlling market data streaming:', error);
            this.showNotification('Error', 'Failed to control streaming', 'error');
        }
    }
    
    updateStreamingStatus(symbol, isStreaming) {
        const statusElement = document.querySelector(`[data-streaming-status="${symbol}"]`);
        if (statusElement) {
            statusElement.textContent = isStreaming ? 'Streaming' : 'Stopped';
            statusElement.className = isStreaming ? 'status-streaming' : 'status-stopped';
        }
        
        const controlElement = document.querySelector(`[data-streaming-action="${isStreaming ? 'stop' : 'start'}"][data-symbol="${symbol}"]`);
        if (controlElement) {
            controlElement.style.display = 'block';
        }
        
        const oppositeControlElement = document.querySelector(`[data-streaming-action="${isStreaming ? 'start' : 'stop'}"][data-symbol="${symbol}"]`);
        if (oppositeControlElement) {
            oppositeControlElement.style.display = 'none';
        }
    }
    
    attemptReconnect(connectionType, url) {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect to ${connectionType} (attempt ${this.reconnectAttempts})`);
            
            setTimeout(() => {
                this.connectWebSocket(connectionType, url);
            }, this.reconnectDelay);
        } else {
            console.error(`Max reconnection attempts reached for ${connectionType}`);
            this.showNotification('Error', `Failed to reconnect to ${connectionType}`, 'error');
        }
    }
    
    showNotification(title, message, type = 'info', category = '') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type} ${category}`;
        notification.innerHTML = `
            <div class="notification-header">
                <span class="notification-title">${title}</span>
                <button class="notification-close">&times;</button>
            </div>
            <div class="notification-message">${message}</div>
        `;
        
        // Add to notifications container
        const container = document.querySelector('.notifications-container') || document.body;
        container.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
        
        // Close button functionality
        const closeButton = notification.querySelector('.notification-close');
        closeButton.addEventListener('click', () => {
            notification.remove();
        });
    }
    
    playAlertSound() {
        // Play alert sound if available
        const audio = new Audio('/static/sounds/alert.mp3');
        audio.play().catch(error => {
            console.log('Could not play alert sound:', error);
        });
    }
    
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];
    }
    
    disconnect() {
        Object.keys(this.connections).forEach(type => {
            if (this.connections[type]) {
                this.connections[type].close();
                this.connections[type] = null;
            }
        });
        this.isConnected = false;
    }
}

// Initialize real-time manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.realTimeManager = new RealTimeManager();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.realTimeManager) {
        window.realTimeManager.disconnect();
    }
});











