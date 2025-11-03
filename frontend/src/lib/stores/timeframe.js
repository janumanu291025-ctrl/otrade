import { writable } from 'svelte/store';

const API_BASE_URL = 'http://localhost:8000';

function createTimeframeStore() {
    const { subscribe, set, update } = writable({
        ltp: 0,
        day_open: 0,
        day_high: 0,
        day_low: 0,
        prev_close: 0,
        timestamp: null,
        timeframes: {},
        loading: false,
        error: null,
        lastUpdate: null
    });

    let updateInterval = null;
    let isMarketHours = false;

    // Check if current time is within market hours (9:15 AM - 3:30 PM IST)
    function checkMarketHours() {
        const now = new Date();
        const hours = now.getHours();
        const minutes = now.getMinutes();
        const currentTime = hours * 60 + minutes;
        
        // Market hours: 9:15 AM (555 minutes) to 3:30 PM (930 minutes)
        const marketOpen = 9 * 60 + 15;  // 555
        const marketClose = 15 * 60 + 30;  // 930
        
        return currentTime >= marketOpen && currentTime <= marketClose;
    }

    async function fetchTimeframeAnalysis() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/strategy/timeframe-analysis`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json();
            
            if (result.status === 'success' && result.data) {
                update(state => ({
                    ...state,
                    ltp: result.data.ltp,
                    day_open: result.data.day_open || 0,
                    day_high: result.data.day_high || 0,
                    day_low: result.data.day_low || 0,
                    prev_close: result.data.prev_close || 0,
                    timestamp: result.data.timestamp,
                    timeframes: result.data.timeframes,
                    lastUpdate: new Date(),
                    error: null
                }));
            }
        } catch (error) {
            console.error('Error fetching timeframe analysis:', error);
            update(state => ({
                ...state,
                error: error.message
            }));
        }
    }

    return {
        subscribe,

        async initialize() {
            // Initial fetch
            await fetchTimeframeAnalysis();
            
            // Start periodic updates
            isMarketHours = checkMarketHours();
            const updateFrequency = isMarketHours ? 1000 : 1000; // 1 second during both market and non-market hours
            
            if (updateInterval) {
                clearInterval(updateInterval);
            }
            
            updateInterval = setInterval(async () => {
                // Check market hours every update
                isMarketHours = checkMarketHours();
                await fetchTimeframeAnalysis();
            }, updateFrequency);
        },

        async refresh() {
            await fetchTimeframeAnalysis();
        },

        destroy() {
            if (updateInterval) {
                clearInterval(updateInterval);
                updateInterval = null;
            }
        },

        // Update from WebSocket (during market hours)
        updateFromWebSocket(data) {
            if (data && data.ltp !== undefined) {
                update(state => ({
                    ...state,
                    ltp: data.ltp,
                    day_open: data.day_open || state.day_open,
                    day_high: data.day_high || state.day_high,
                    day_low: data.day_low || state.day_low,
                    prev_close: data.prev_close || state.prev_close,
                    timestamp: data.timestamp,
                    timeframes: data.timeframes || state.timeframes,
                    lastUpdate: new Date()
                }));
            }
        }
    };
}

export const timeframeAnalysis = createTimeframeStore();
