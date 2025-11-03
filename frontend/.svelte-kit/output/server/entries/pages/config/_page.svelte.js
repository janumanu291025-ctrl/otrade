import { c as create_ssr_component, d as each, e as escape } from "../../../chunks/ssr.js";
import "../../../chunks/api.js";
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let configs = [];
  return `<div class="container mx-auto p-6"><div class="flex justify-between items-center mb-6"><div data-svelte-h="svelte-1iybckf"><h1 class="text-3xl font-bold text-gray-800">Trading Configuration</h1> <p class="text-gray-600 mt-2">Unified configuration used by Backtest, Paper Trading, and Live Trading</p></div> <button class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition" ${""}>New Configuration</button></div> ${``} ${`<div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6" data-svelte-h="svelte-u69ebj"><p class="text-yellow-800">⚠ No active configuration. Please create or activate a configuration.</p></div>`}  ${``}  <div class="bg-white rounded-lg shadow-lg p-6"><h2 class="text-2xl font-bold mb-4" data-svelte-h="svelte-o7f8wo">All Configurations</h2> ${`${configs.length === 0 ? `<div class="text-center py-8 text-gray-500" data-svelte-h="svelte-1u0u649">No configurations found. Create your first configuration to get started.</div>` : `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">${each(configs, (config) => {
    return `<div class="${"border rounded-lg p-4 " + escape(
      config.is_active ? "border-green-500 bg-green-50" : "border-gray-200",
      true
    )}"><div class="flex items-start justify-between mb-2"><div class="flex-1"><h3 class="font-semibold text-lg">${escape(config.name)}</h3> ${config.description ? `<p class="text-sm text-gray-600 mt-1">${escape(config.description)}</p>` : ``}</div> ${config.is_active ? `<span class="px-2 py-1 text-xs bg-green-600 text-white rounded" data-svelte-h="svelte-1dbato0">Active</span>` : ``}</div> <div class="mt-3 space-y-1 text-sm text-gray-600"><div>Capital: ₹${escape(config.initial_capital.toLocaleString())}</div> <div>MA: ${escape(config.ma_short_period)}/${escape(config.ma_long_period)}</div> <div>Timeframes: ${escape(config.major_trend_timeframe)} / ${escape(config.minor_trend_timeframe)}</div></div> <div class="mt-4 flex space-x-2">${!config.is_active ? `<button class="flex-1 px-3 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition" ${""}>Activate
								</button>` : ``} <button class="flex-1 px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition" ${""}>Edit</button> <button class="px-3 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700 transition" ${""}>Delete
							</button></div> </div>`;
  })}</div>`}`}</div> </div>`;
});
export {
  Page as default
};
