import { d as derived, w as writable } from "./index.js";
function createWebSocketStore() {
  const { subscribe, set, update } = writable({
    connected: false,
    ws: null,
    messages: [],
    marketData: {},
    // instrument_token -> latest tick data
    subscriptions: {}
    // source -> instrument_tokens
  });
  let ws = null;
  let reconnectInterval = null;
  let pingInterval = null;
  function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      return;
    }
    ws = new WebSocket("ws://localhost:8000/ws");
    ws.onopen = () => {
      console.log("WebSocket connected");
      update((state) => ({ ...state, connected: true, ws }));
      if (reconnectInterval) {
        clearInterval(reconnectInterval);
        reconnectInterval = null;
      }
      if (pingInterval) {
        clearInterval(pingInterval);
      }
      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping", timestamp: Date.now() }));
        }
      }, 3e4);
    };
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log("[WebSocket] Received message:", message.type, message);
      if (message.type === "market_data") {
        console.log("[WebSocket] Market data received:", message.data.length, "ticks");
        update((state) => {
          const marketData2 = { ...state.marketData };
          message.data.forEach((tick) => {
            const token = tick.instrument_token;
            const price = tick.last_price / 100;
            console.log(`[WebSocket] Token ${token}: ₹${price.toFixed(2)}`);
            marketData2[token] = {
              ...tick,
              last_update: (/* @__PURE__ */ new Date()).toISOString()
            };
          });
          return {
            ...state,
            marketData: marketData2,
            messages: [...state.messages, message]
          };
        });
        import("./timeframe.js").then((module) => {
          if (module.timeframeAnalysis) ;
        }).catch(() => {
        });
      } else {
        update((state) => ({
          ...state,
          messages: [...state.messages, message]
        }));
      }
    };
    ws.onclose = () => {
      console.log("WebSocket disconnected");
      update((state) => ({ ...state, connected: false, ws: null }));
      if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
      }
      if (!reconnectInterval) {
        reconnectInterval = setInterval(() => {
          console.log("Attempting to reconnect...");
          connect();
        }, 5e3);
      }
    };
    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
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
    update((state) => ({ ...state, connected: false, ws: null }));
  }
  function send(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    } else {
      console.warn("WebSocket not connected, cannot send message");
    }
  }
  function subscribeMarketData(source, instruments, mode = "quote") {
    if (!Array.isArray(instruments) || instruments.length === 0) {
      console.warn("No instruments to subscribe");
      return;
    }
    send({
      type: "subscribe_market_data",
      source,
      instruments,
      mode
      // 'ltp', 'quote', or 'full'
    });
    update((state) => ({
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
      type: "unsubscribe_market_data",
      source,
      instruments
    });
    update((state) => {
      const subscriptions = { ...state.subscriptions };
      delete subscriptions[source];
      return { ...state, subscriptions };
    });
    console.log(`Unsubscribed from ${source}`);
  }
  function getLatestPrice(instrumentToken) {
    let latestPrice = null;
    update((state) => {
      const tick = state.marketData[instrumentToken];
      if (tick) {
        latestPrice = tick.last_price / 100;
      }
      return state;
    });
    return latestPrice;
  }
  function getMarketData(instrumentToken) {
    let data = null;
    update((state) => {
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
const websocket = createWebSocketStore();
const marketData = derived(
  websocket,
  ($websocket) => $websocket.marketData
);
export {
  marketData as m,
  websocket as w
};
