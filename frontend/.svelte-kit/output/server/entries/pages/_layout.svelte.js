import { c as create_ssr_component, a as subscribe, e as escape } from "../../chunks/ssr.js";
/* empty css               */
import { d as derived, w as writable } from "../../chunks/index.js";
import { b as broker } from "../../chunks/broker.js";
function createWebSocketStore() {
  const { subscribe: subscribe2, set, update } = writable({
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
          const marketData = { ...state.marketData };
          message.data.forEach((tick) => {
            const token = tick.instrument_token;
            const price = tick.last_price / 100;
            console.log(`[WebSocket] Token ${token}: ₹${price.toFixed(2)}`);
            marketData[token] = {
              ...tick,
              last_update: (/* @__PURE__ */ new Date()).toISOString()
            };
          });
          return {
            ...state,
            marketData,
            messages: [...state.messages, message]
          };
        });
        import("../../chunks/timeframe.js").then((module) => {
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
    subscribe: subscribe2,
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
derived(
  websocket,
  ($websocket) => $websocket.marketData
);
const Layout = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $broker, $$unsubscribe_broker;
  $$unsubscribe_broker = subscribe(broker, (value) => $broker = value);
  $$unsubscribe_broker();
  return `<div class="min-h-screen flex bg-gray-50"> <aside class="w-64 bg-white shadow-lg border-r border-gray-200"><div class="p-6 border-b border-gray-200"><div class="flex items-center gap-2"><h1 class="text-2xl font-bold text-blue-600" data-svelte-h="svelte-93xwkk">OTrade</h1> <div class="${"w-3 h-3 rounded-full " + escape($broker.connected ? "bg-green-500" : "bg-red-500", true)}"></div></div></div> <nav class="p-4 space-y-1" data-svelte-h="svelte-ug49b7"><a href="/" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150"><span class="text-xl">🏠</span> <span class="font-medium">Home</span></a> <a href="/config" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150"><span class="text-xl">⚙️</span> <span class="font-medium">Config</span></a> <a href="/paper-trading" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150"><span class="text-xl">📄</span> <span class="font-medium">Mock</span></a> <a href="/live-trading-v2" class="flex items-center gap-3 px-4 py-3 rounded-lg text-red-700 hover:bg-red-50 hover:text-red-600 transition-colors duration-150 font-semibold"><span class="text-xl">🔴</span> <span class="font-medium">Live</span></a></nav></aside>  <main class="flex-1 overflow-auto"><div class="p-8">${slots.default ? slots.default({}) : ``}</div></main></div>`;
});
export {
  Layout as default
};
