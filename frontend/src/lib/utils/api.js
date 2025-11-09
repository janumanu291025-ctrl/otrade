import axios from 'axios';

const BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
    baseURL: BASE_URL,
    headers: {
        'Content-Type': 'application/json'
    }
});

// Broker API
export const brokerAPI = {
    getConfig: (brokerType) => api.get(`/broker/config/${brokerType}`),
    createConfig: (data) => api.post('/broker/config', data),
    initConfig: (brokerType) => api.post(`/broker/init/${brokerType}`),
    getAuthUrl: (brokerType) => api.get(`/broker/auth-url/${brokerType}`),
    getProfile: (brokerType) => api.get(`/broker/profile/${brokerType}`),
    getFunds: (brokerType) => api.get(`/broker/funds/${brokerType}`),
    downloadInstruments: (brokerType, exchange = null) => 
        api.post(`/broker/instruments/download/${brokerType}`, null, { params: exchange ? { exchange } : {} }),
    getInstruments: (params = {}) => 
        api.get('/broker/instruments', { params }),
    getInstrumentsStats: () => api.get('/broker/instruments/stats'),
    getQuote: (brokerType, instruments) => {
        // Convert array to comma-separated string
        const instrumentsStr = Array.isArray(instruments) ? instruments.join(',') : instruments;
        return api.get(`/broker/quote/${brokerType}`, { 
            params: { instruments: instrumentsStr }
        });
    },
    disconnect: (brokerType) => api.post(`/broker/disconnect/${brokerType}`),
    getStatus: (brokerType) => api.get(`/broker/status/${brokerType}`),
    getEnvConfig: (brokerType) => api.get(`/broker/env-config/${brokerType}`),
    updateEnvConfig: (brokerType, data) => api.post(`/broker/env-config/${brokerType}`, data),
    getNifty50: () => api.get('/broker/nifty50')
};

// Portfolio API - Positions and fund management
export const portfolioAPI = {
    // Get short-term positions (derivatives and intraday equity)
    getPositions: () => api.get('/portfolio/positions'),
    
    // Fund management
    getFund: () => api.get('/portfolio/fund'),
    getFundSummary: (brokerType = 'kite') => api.get('/portfolio/fund/summary', { params: { broker_type: brokerType } }),
    syncFund: (brokerType = 'kite') => api.post('/portfolio/fund/sync', null, { params: { broker_type: brokerType } })
};

// Unified Trading Configuration API (replaces old strategy/orders/positions APIs)
export const configAPI = {
    getAll: () => api.get('/config/'),
    getActive: () => api.get('/config/active'),
    get: (id) => api.get(`/config/${id}`),
    create: (data) => api.post('/config/', data),
    update: (id, data) => api.put(`/config/${id}`, data),
    activate: (id) => api.post(`/config/${id}/activate`),
    delete: (id) => api.delete(`/config/${id}`)
};

// Market Hours API
export const marketHoursAPI = {
    getStatus: () => api.get('/market-time/status'),
    isTradingDay: (date = null) => api.get('/market-time/is-trading-day', { params: date ? { date } : {} }),
    getNextTradingDay: (fromDate = null) => api.get('/market-time/next-trading-day', { params: fromDate ? { from_date: fromDate } : {} })
};

// Paper Trading API
export const paperTradingAPI = {
    // Engine control
    start: (data) => api.post('/paper-trading/start', data),
    stop: () => api.post('/paper-trading/stop'),
    pause: () => api.post('/paper-trading/pause'),
    resume: () => api.post('/paper-trading/resume'),
    getStatus: () => api.get('/paper-trading/status'),
    getMarketStatus: () => api.get('/paper-trading/market-status'),
    
    // Trading operations
    suspendCE: (suspend) => api.post('/paper-trading/suspend-ce', null, { params: { suspend } }),
    suspendPE: (suspend) => api.post('/paper-trading/suspend-pe', null, { params: { suspend } }),
    closePosition: (tradeId) => api.post(`/paper-trading/close-position/${tradeId}`),
    
    // Data fetching
    getTrades: (configId, params = {}) => api.get(`/paper-trading/trades/${configId}`, { params }),
    getAlerts: (configId, params = {}) => api.get(`/paper-trading/alerts/${configId}`, { params }),
    getMarketData: (configId, params = {}) => api.get(`/paper-trading/market-data/${configId}`, { params })
};

// Live Trading API
export const liveTradingAPI = {
    // Engine control
    start: (configId) => api.post('/live-trading/start', null, { params: { config_id: configId } }),
    stop: () => api.post('/live-trading/stop'),
    pause: () => api.post('/live-trading/pause'),
    resume: () => api.post('/live-trading/resume'),
    getStatus: () => api.get('/live-trading/status'),
    
    // Positions management
    getPositions: (params = {}) => api.get('/live-trading/positions', { params }),
    closePosition: (tradeId) => api.post(`/live-trading/positions/${tradeId}/close`),
    closeAllPositions: (configId = null) => 
        api.post('/live-trading/positions/close-all', null, configId ? { params: { config_id: configId } } : {}),
    modifyTarget: (tradeId, newTargetPrice) => 
        api.put(`/live-trading/positions/${tradeId}/modify-target`, { new_target_price: newTargetPrice }),
    cancelSellOrder: (tradeId) => api.post(`/live-trading/positions/${tradeId}/cancel-sell-order`),
    
    // Data fetching
    getNotifications: (params = {}) => api.get('/live-trading/notifications', { params }),
    getMarketData: (configId, params = {}) => 
        api.get('/live-trading/market-data', { params: { ...params, config_id: configId } }),
    getSignals: (configId, params = {}) => 
        api.get('/live-trading/signals', { params: { ...params, config_id: configId } }),
    getStatistics: (configId) => api.get('/live-trading/statistics', { params: { config_id: configId } }),
    getIndicators: () => api.get('/live-trading/indicators'),
    
    // Configuration
    suspendCE: (configId, suspend) => api.post(`/live-trading/configs/${configId}/suspend-ce`, suspend),
    suspendPE: (configId, suspend) => api.post(`/live-trading/configs/${configId}/suspend-pe`, suspend)
};

// Live Trading V2 API
export const liveTradingV2API = {
    // Engine control
    start: (configId, contractExpiry = null) => 
        api.post('/live-trading-v2/start', null, { 
            params: { 
                config_id: configId, 
                ...(contractExpiry && { contract_expiry: contractExpiry })
            } 
        }),
    stop: () => api.post('/live-trading-v2/stop'),
    pause: () => api.post('/live-trading-v2/pause'),
    resume: () => api.post('/live-trading-v2/resume'),
    getStatus: () => api.get('/live-trading-v2/status'),
    
    // Trading operations
    suspendCE: (suspend) => api.post('/live-trading-v2/suspend-ce', { suspend }),
    suspendPE: (suspend) => api.post('/live-trading-v2/suspend-pe', { suspend }),
    closePosition: (tradeId, reason = 'manual_close') => 
        api.post('/live-trading-v2/close-position', { trade_id: tradeId, reason }),
    reconcile: () => api.post('/live-trading-v2/reconcile'),
    
    // Data fetching
    getTrades: (params = {}) => api.get('/live-trading-v2/trades', { params }),
    getPositions: () => api.get('/live-trading-v2/positions'),
    getOrders: () => api.get('/live-trading-v2/orders'),
    getAlerts: (params = {}) => api.get('/live-trading-v2/alerts', { params }),
    getSignals: (params = {}) => api.get('/live-trading-v2/signals', { params }),
    getInstruments: (configId) => api.get(`/live-trading-v2/instruments/${configId}`),
    getMarketData: () => api.get('/live-trading-v2/market-data'),
    getCandles: (params = {}) => api.get('/live-trading-v2/candles', { params }),
    getChartData: (params = {}) => api.get('/live-trading-v2/chart-data', { params }),
    
    // Performance
    getPerformance: () => api.get('/live-trading-v2/performance')
};

export default api;
