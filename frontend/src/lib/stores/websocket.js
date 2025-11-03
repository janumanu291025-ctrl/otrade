import { writable, derived } from 'svelte/store';

function createWebSocketStore() {
    const { subscribe, set, update } = writable({
        connected: false,
        ws: null,
        messages: [],
        marketData: {},  // instrument_token -> latest tick data
        subscriptions: {}  // source -> instrument_tokens
    });

    let ws = null;
    let reconnectInterval = null;
    let pingInterval = null;

    function connect() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            return;
        }

        ws = new WebSocket('ws://localhost:8000/ws');

        ws.onopen = () => {
            console.log('WebSocket connected');
            update(state => ({ ...state, connected: true, ws }));
            
            if (reconnectInterval) {
                clearInterval(reconnectInterval);
                reconnectInterval = null;
            }

            // Send ping every 30 seconds
            if (pingInterval) {
                clearInterval(pingInterval);
            }
            pingInterval = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
                }
            }, 30000);
        };

        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            console.log('[WebSocket] Received message:', message.type, message);
            
            // Handle market data separately
            if (message.type === 'market_data') {
                console.log('[WebSocket] Market data received:', message.data.length, 'ticks');
                update(state => {
                    const marketData = { ...state.marketData };
                    
                    // Update market data for each instrument
                    message.data.forEach(tick => {
                        const token = tick.instrument_token;
                        const price = tick.last_price / 100;
                        console.log(`[WebSocket] Token ${token}: ₹${price.toFixed(2)}`);
                        marketData[token] = {
                            ...tick,
                            last_update: new Date().toISOString()
                        };
                    });
                    
                    return {
                        ...state,
                        marketData,
                        messages: [...state.messages, message]
                    };
                });
                
                // Forward to timeframe analyzer store if available
                import('$lib/stores/timeframe').then(module => {
                    if (module.timeframeAnalysis) {
                        // The timeframe analyzer will be updated via backend WebSocket broadcast
                        // This is just for informational updates
                    }
                }).catch(() => {
                    // Timeframe store not available
                });
            } else {
                // Other message types
                update(state => ({
                    ...state,
                    messages: [...state.messages, message]
                }));
            }
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            update(state => ({ ...state, connected: false, ws: null }));
            
            if (pingInterval) {
                clearInterval(pingInterval);
                pingInterval = null;
            }
            
            // Attempt to reconnect every 5 seconds
            if (!reconnectInterval) {
                reconnectInterval = setInterval(() => {
                    console.log('Attempting to reconnect...');
                    connect();
                }, 5000);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    function disconnect() {
        if (ws) {
            ws.close();
            ws = null;
        }
        if (reconnectInterval) {
            clearInterval(reconnectInterval);
            reconnectInterval = null;
        }
        if (pingInterval) {
            clearInterval(pingInterval);
            pingInterval = null;
        }
        update(state => ({ ...state, connected: false, ws: null }));
    }

    function send(message) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not connected, cannot send message');
        }
    }

    function subscribeMarketData(source, instruments, mode = 'quote') {
        if (!Array.isArray(instruments) || instruments.length === 0) {
            console.warn('No instruments to subscribe');
            return;
        }
        
        send({
            type: 'subscribe_market_data',
            source: source,
            instruments: instruments,
            mode: mode  // 'ltp', 'quote', or 'full'
        });
        
        // Track subscription
        update(state => ({
            ...state,
            subscriptions: {
                ...state.subscriptions,
                [source]: instruments
            }
        }));
        
        console.log(`Subscribed to ${instruments.length} instruments from ${source} in '${mode}' mode`);
    }

    function unsubscribeMarketData(source, instruments = null) {
        send({
            type: 'unsubscribe_market_data',
            source: source,
            instruments: instruments
        });
        
        // Remove from tracking
        update(state => {
            const subscriptions = { ...state.subscriptions };
            delete subscriptions[source];
            return { ...state, subscriptions };
        });
        
        console.log(`Unsubscribed from ${source}`);
    }

    function getLatestPrice(instrumentToken) {
        let latestPrice = null;
        update(state => {
            const tick = state.marketData[instrumentToken];
            if (tick) {
                latestPrice = tick.last_price / 100;  // Convert from paise to rupees
            }
            return state;
        });
        return latestPrice;
    }

    function getMarketData(instrumentToken) {
        let data = null;
        update(state => {
            data = state.marketData[instrumentToken];
            return state;
        });
        return data;
    }

    return {
        subscribe,
        connect,
        disconnect,
        send,
        subscribeMarketData,
        unsubscribeMarketData,
        getLatestPrice,
        getMarketData
    };
}

export const websocket = createWebSocketStore();

// Derived store for market data only
export const marketData = derived(
    websocket,
    $websocket => $websocket.marketData
);

// Helper function to format price from paise to rupees
export function formatPrice(paise) {
    if (paise === null || paise === undefined) return null;
    return (paise / 100).toFixed(2);
}

// Helper function to format quantity
export function formatQuantity(qty) {
    if (qty === null || qty === undefined) return 0;
    return qty;
}
