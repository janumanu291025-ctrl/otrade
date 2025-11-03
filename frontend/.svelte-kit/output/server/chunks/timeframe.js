import { w as writable } from "./index.js";
const API_BASE_URL = "http://localhost:8000";
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
  function checkMarketHours() {
    const now = /* @__PURE__ */ new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const currentTime = hours * 60 + minutes;
    const marketOpen = 9 * 60 + 15;
    const marketClose = 15 * 60 + 30;
    return currentTime >= marketOpen && currentTime <= marketClose;
  }
  async function fetchTimeframeAnalysis() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/strategy/timeframe-analysis`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      if (result.status === "success" && result.data) {
        update((state) => ({
          ...state,
          ltp: result.data.ltp,
          day_open: result.data.day_open || 0,
          day_high: result.data.day_high || 0,
          day_low: result.data.day_low || 0,
          prev_close: result.data.prev_close || 0,
          timestamp: result.data.timestamp,
          timeframes: result.data.timeframes,
          lastUpdate: /* @__PURE__ */ new Date(),
          error: null
        }));
      }
    } catch (error) {
      console.error("Error fetching timeframe analysis:", error);
      update((state) => ({
        ...state,
        error: error.message
      }));
    }
  }
  return {
    subscribe,
    async initialize() {
      await fetchTimeframeAnalysis();
      isMarketHours = checkMarketHours();
      const updateFrequency = isMarketHours ? 1e3 : 1e3;
      if (updateInterval) {
        clearInterval(updateInterval);
      }
      updateInterval = setInterval(async () => {
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
      if (data && data.ltp !== void 0) {
        update((state) => ({
          ...state,
          ltp: data.ltp,
          day_open: data.day_open || state.day_open,
          day_high: data.day_high || state.day_high,
          day_low: data.day_low || state.day_low,
          prev_close: data.prev_close || state.prev_close,
          timestamp: data.timestamp,
          timeframes: data.timeframes || state.timeframes,
          lastUpdate: /* @__PURE__ */ new Date()
        }));
      }
    }
  };
}
const timeframeAnalysis = createTimeframeStore();
export {
  timeframeAnalysis
};
