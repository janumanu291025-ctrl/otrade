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
    getOrders: (brokerType) => api.get(`/broker/orders/${brokerType}`),
    getTrades: (brokerType) => api.get(`/broker/trades/${brokerType}`),
    getPositions: (brokerType) => api.get(`/broker/positions/${brokerType}`),
    getNifty50: () => api.get('/broker/nifty50')
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
    getConfig: () => api.get('/market-time/config'),
    updateConfig: (data) => api.put('/market-time/config', data),
    getStatus: () => api.get('/market-time/status'),
    getHolidays: (year = null) => api.get('/market-time/holidays', { params: year ? { year } : {} }),
    addHoliday: (data) => api.post('/market-time/holidays', data),
    removeHoliday: (date) => api.delete(`/market-time/holidays/${date}`)
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

export default api;
