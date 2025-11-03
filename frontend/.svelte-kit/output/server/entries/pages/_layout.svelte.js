import { c as create_ssr_component, a as subscribe, e as escape } from "../../chunks/ssr.js";
import "../../chunks/websocket.js";
import { b as broker } from "../../chunks/broker.js";
const Layout = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $broker, $$unsubscribe_broker;
  $$unsubscribe_broker = subscribe(broker, (value) => $broker = value);
  $$unsubscribe_broker();
  return `<div class="min-h-screen flex bg-gray-50"> <aside class="w-64 bg-white shadow-lg border-r border-gray-200"><div class="p-6 border-b border-gray-200"><div class="flex items-center gap-2"><h1 class="text-2xl font-bold text-blue-600" data-svelte-h="svelte-93xwkk">OTrade</h1> <div class="${"w-3 h-3 rounded-full " + escape($broker.connected ? "bg-green-500" : "bg-red-500", true)}"></div></div> <p class="text-sm text-gray-600 mt-1" data-svelte-h="svelte-1ol7gua">Algorithmic Trading</p></div> <nav class="p-4 space-y-1" data-svelte-h="svelte-1oqv0y2"><a href="/" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150"><span class="text-xl">🏠</span> <span class="font-medium">Home</span></a> <a href="/config" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150"><span class="text-xl">⚙️</span> <span class="font-medium">Configuration</span></a> <a href="/paper-trading" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150"><span class="text-xl">📄</span> <span class="font-medium">Paper Trade</span></a> <a href="/live-trade" class="flex items-center gap-3 px-4 py-3 rounded-lg text-red-700 hover:bg-red-50 hover:text-red-600 transition-colors duration-150 font-semibold"><span class="text-xl">🔴</span> <span class="font-medium">Live Trading</span></a></nav></aside>  <main class="flex-1 overflow-auto"><div class="p-8">${slots.default ? slots.default({}) : ``}</div></main></div>`;
});
export {
  Layout as default
};
