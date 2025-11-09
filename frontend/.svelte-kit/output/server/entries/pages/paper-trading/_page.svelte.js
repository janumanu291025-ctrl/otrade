import { c as create_ssr_component, o as onDestroy, e as escape, f as each, b as add_attribute } from "../../../chunks/ssr.js";
import "../../../chunks/api.js";
function formatCurrency(value) {
  return new Intl.NumberFormat(
    "en-IN",
    {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }
  ).format(value);
}
function getStatusColor(status) {
  const colors = {
    "running": "text-green-600 bg-green-100",
    "paused": "text-yellow-600 bg-yellow-100",
    "stopped": "text-gray-600 bg-gray-100"
  };
  return colors[status];
}
function getTrendColor(trend) {
  return "text-gray-500";
}
function getTrendDotColor(trend) {
  return "bg-gray-400";
}
function formatTrend(trend) {
  return "-";
}
function getPnLColor(pnl) {
  return "text-gray-600";
}
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let engineStatus = {
    status: "stopped",
    initial_capital: 0,
    current_capital: 0,
    major_timeframe: "15min",
    minor_timeframe: "1min"
  };
  let performance = {
    total_trades: 0,
    call_trades: 0,
    put_trades: 0,
    realized_pnl: 0,
    unrealized_pnl: 0,
    total_pnl: 0,
    win_rate: 0
  };
  let activeTrades = [];
  let closedTrades = [];
  let configs = [];
  let enableHistoricalMode = false;
  let instruments = [];
  onDestroy(() => {
  });
  return `<div class="space-y-6"> <div class="flex justify-between items-center"><div data-svelte-h="svelte-flwklp"><h1 class="text-3xl font-bold text-gray-900">Mock</h1> <p class="text-gray-600 mt-1">Real-time mock trading with live market data</p></div> <div class="flex items-center gap-3"> ${``}  <div class="${"px-4 py-2 rounded-lg " + escape(getStatusColor(engineStatus.status), true) + " font-semibold"}">${escape(engineStatus.status.toUpperCase())}</div></div></div>  <div class="border-b border-gray-200"><div class="flex gap-1 p-2"><button class="${"px-6 py-3 rounded-t-lg font-medium transition-colors " + escape(
    "bg-blue-600 text-white",
    true
  )}">🏠 Dashboard</button> <button class="${"px-6 py-3 rounded-t-lg font-medium transition-colors " + escape(
    "text-gray-600 hover:bg-gray-100",
    true
  )}">📊 Trades</button></div></div>  ${``}  ${`<div class="grid grid-cols-1 lg:grid-cols-3 gap-6"> <div class="bg-white rounded-lg shadow-md p-6"><h2 class="text-xl font-bold mb-4" data-svelte-h="svelte-1mjetow">Controls</h2> <div class="mb-4"><label for="config-select" class="block text-sm font-medium text-gray-700 mb-2" data-svelte-h="svelte-bdv5vt">Configuration</label> <select id="config-select" ${""} class="w-full px-4 py-2 border rounded-lg disabled:bg-gray-100">${each(configs, (config) => {
    return `<option${add_attribute("value", config.id, 0)}>${escape(config.name)}</option>`;
  })}</select> <p class="text-xs text-gray-600 mt-2" data-svelte-h="svelte-1diujsv">Manage configurations on the <a href="/config" class="text-blue-600 hover:underline font-semibold">Config</a> page.</p></div>  ${`<div class="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200"><label class="flex items-start gap-3 cursor-pointer"><input type="checkbox" ${""} class="w-5 h-5 mt-0.5"${add_attribute("checked", enableHistoricalMode, 1)}> <div class="flex-1"><span class="text-sm font-medium text-gray-900" data-svelte-h="svelte-x0okoj">Enable Historical Simulation</span> <p class="text-xs text-gray-600 mt-1">${`Replay historical market data for practice (Market is closed)`}</p> ${``}</div></label>  ${``}</div>`} <div class="space-y-2">${`<button ${"disabled"} class="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 font-semibold">▶ Start Trading</button>`} ${``}</div> ${``}</div>  <div class="lg:col-span-2 bg-white rounded-lg shadow-md p-6"><div class="flex justify-between items-center mb-4"><h2 class="text-xl font-bold">Nifty 50
							${``} ${``}</h2> <div class="${"text-sm font-medium " + escape(
    "text-gray-500",
    true
  )}">${escape("🔴 Market Closed")}</div></div> <div class="grid grid-cols-1 gap-4"> <div class="bg-white rounded-lg border border-gray-200 overflow-hidden"><div class="overflow-x-auto"><table class="w-full"><thead class="bg-gray-50" data-svelte-h="svelte-nbuv8m"><tr><th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Indicator</th> <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Trend</th> <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">T.frame</th> <th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">7 MA</th> <th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">20 MA</th> <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Last Changed</th></tr></thead> <tbody class="divide-y divide-gray-200"> <tr class="hover:bg-gray-50"><td class="px-4 py-3"><div class="flex items-center gap-2"><div class="${"w-3 h-3 " + escape(getTrendDotColor(), true) + " rounded-full"}"></div> <span class="text-sm font-medium text-gray-900" data-svelte-h="svelte-d7i8d0">Major</span></div></td> <td class="px-4 py-3"><span class="${"px-2 py-1 text-xs font-semibold rounded-full " + escape(getTrendColor(), true) + " bg-opacity-10"}">${escape(formatTrend())}</span></td> <td class="px-4 py-3 text-sm text-gray-700">${escape(engineStatus.major_timeframe)}</td> <td class="px-4 py-3 text-sm text-right font-medium text-gray-900">${escape("-")}</td> <td class="px-4 py-3 text-sm text-right font-medium text-gray-900">${escape("-")}</td> <td class="px-4 py-3 text-sm text-gray-700">${escape("-")}</td></tr>  <tr class="hover:bg-gray-50"><td class="px-4 py-3"><div class="flex items-center gap-2"><div class="${"w-3 h-3 " + escape(getTrendDotColor(), true) + " rounded-full"}"></div> <span class="text-sm font-medium text-gray-900" data-svelte-h="svelte-ot51so">Minor</span></div></td> <td class="px-4 py-3"><span class="${"px-2 py-1 text-xs font-semibold rounded-full " + escape(getTrendColor(), true) + " bg-opacity-10"}">${escape(formatTrend())}</span></td> <td class="px-4 py-3 text-sm text-gray-700">${escape(engineStatus.minor_timeframe)}</td> <td class="px-4 py-3 text-sm text-right font-medium text-gray-900">${escape("-")}</td> <td class="px-4 py-3 text-sm text-right font-medium text-gray-900">${escape("-")}</td> <td class="px-4 py-3 text-sm text-gray-700">${escape("-")}</td></tr></tbody></table></div></div>  <div class="bg-white rounded-lg border border-gray-200 overflow-hidden"> <div class="border-b border-gray-200 bg-gray-50"><div class="flex"><button class="${"flex-1 px-4 py-3 text-sm font-medium transition-colors " + escape(
    "bg-blue-600 text-white",
    true
  )}">Instruments (${escape(instruments.length)})</button> <button class="${"flex-1 px-4 py-3 text-sm font-medium transition-colors " + escape(
    "text-gray-600 hover:bg-gray-100",
    true
  )}">Open Orders (${escape(activeTrades.length)})</button> <button class="${"flex-1 px-4 py-3 text-sm font-medium transition-colors " + escape(
    "text-gray-600 hover:bg-gray-100",
    true
  )}">Closed Orders (${escape(closedTrades.length)})</button> <button class="${"flex-1 px-4 py-3 text-sm font-medium transition-colors " + escape(
    "text-gray-600 hover:bg-gray-100",
    true
  )}">Positions (${escape(0)})</button></div></div>  <div class="max-h-64 overflow-y-auto">${` ${instruments.length === 0 ? `<div class="text-center py-8 text-gray-500 text-sm" data-svelte-h="svelte-16txvva">No instruments available</div>` : `<table class="w-full"><thead class="bg-gray-50 sticky top-0" data-svelte-h="svelte-1l8q3zb"><tr><th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Type</th> <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Symbol</th> <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Strike</th> <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">LTP</th> <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Qty</th> <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Value</th> <th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Cash After</th> <th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Triggers</th></tr></thead> <tbody class="divide-y divide-gray-200">${each(instruments, (instrument) => {
    return `<tr class="${"hover:bg-gray-50 " + escape(instrument.type === "INDEX" ? "bg-blue-50" : "", true)}"><td class="px-3 py-2">${instrument.type === "INDEX" ? `<span class="px-1.5 py-0.5 text-xs font-semibold rounded bg-blue-100 text-blue-700" data-svelte-h="svelte-agm0hh">INDEX
																</span>` : `${instrument.type === "CE" ? `<span class="px-1.5 py-0.5 text-xs font-semibold rounded bg-green-100 text-green-700" data-svelte-h="svelte-1lx8y5f">CE
																</span>` : `${instrument.type === "PE" ? `<span class="px-1.5 py-0.5 text-xs font-semibold rounded bg-red-100 text-red-700" data-svelte-h="svelte-1co5v0k">PE
																</span>` : ``}`}`}</td> <td class="px-3 py-2 text-xs font-medium text-gray-900"${add_attribute("title", instrument.tradingsymbol, 0)}>${escape(instrument.symbol)}</td> <td class="px-3 py-2 text-xs text-right text-gray-700">${escape(instrument.strike ? instrument.strike : "-")}</td> <td class="px-3 py-2 text-xs text-right font-medium text-gray-900">${escape(instrument.ltp ? formatCurrency(instrument.ltp) : "-")}</td> <td class="px-3 py-2 text-xs text-right text-gray-700">${escape(instrument.expected_quantity || "-")}</td> <td class="px-3 py-2 text-xs text-right text-gray-700">${escape(instrument.position_value ? formatCurrency(instrument.position_value) : "-")}</td> <td class="px-3 py-2 text-xs text-right text-gray-700">${escape(instrument.cash_balance_after ? formatCurrency(instrument.cash_balance_after) : "-")}</td> <td class="px-3 py-2 text-xs text-gray-700">${instrument.entry_triggers && instrument.entry_triggers.length > 0 ? `${instrument.entry_triggers.includes("SUSPENDED") ? `<span class="px-1.5 py-0.5 text-xs font-semibold rounded bg-gray-200 text-gray-600" data-svelte-h="svelte-1d82xoo">SUSPENDED
																	</span>` : `<span class="text-xs text-gray-600">${escape(instrument.entry_triggers.join(", "))} </span>`}` : `-`}</td> </tr>`;
  })}</tbody></table>`}`}</div></div></div></div>  <div class="bg-white rounded-lg shadow-md p-6"><h2 class="text-xl font-bold mb-4" data-svelte-h="svelte-2m5op8">Performance</h2> <div class="overflow-x-auto"><table class="w-full border-collapse"><tbody> <tr class="border-b border-gray-200"><td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50" data-svelte-h="svelte-nj5hkm">Trade</td> <td class="px-4 py-3 text-right"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-1es2wmm">Call</div> <div class="text-lg font-bold text-green-600">${escape(performance.call_trades)}</div></td> <td class="px-4 py-3 text-right"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-yl43dr">Put</div> <div class="text-lg font-bold text-red-600">${escape(performance.put_trades)}</div></td> <td class="px-4 py-3 text-right"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-jylfye">Total</div> <div class="text-lg font-bold text-blue-600">${escape(performance.total_trades)}</div></td></tr>  <tr class="border-b border-gray-200"><td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50" data-svelte-h="svelte-j4rhci">P&amp;L</td> <td class="px-4 py-3 text-right"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-121xmxk">Realized</div> <div class="${"text-lg font-bold " + escape(getPnLColor(), true)}">${escape(formatCurrency(performance.realized_pnl))}</div></td> <td class="px-4 py-3 text-right"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-13xmrrf">Unrealized</div> <div class="${"text-lg font-bold " + escape(getPnLColor(), true)}">${escape(formatCurrency(performance.unrealized_pnl))}</div></td> <td class="px-4 py-3 text-right"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-jylfye">Total</div> <div class="${"text-lg font-bold " + escape(getPnLColor(), true)}">${escape(formatCurrency(performance.total_pnl))}</div></td></tr>  <tr class="border-b border-gray-200"><td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50" data-svelte-h="svelte-1xnbmb5">Open bal</td> <td colspan="3" class="px-4 py-3 text-right"><div class="text-xl font-bold text-gray-900">${escape(formatCurrency(engineStatus.initial_capital))}</div></td></tr>  <tr class="border-b border-gray-200"><td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50" data-svelte-h="svelte-2zwkpa">Avl bal</td> <td colspan="3" class="px-4 py-3 text-right"><div class="text-xl font-bold text-blue-600">${escape(formatCurrency(engineStatus.current_capital))}</div></td></tr>  <tr><td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50" data-svelte-h="svelte-18xnug8">Win Rate</td> <td colspan="3" class="px-4 py-3 text-right"><div class="text-xl font-bold text-purple-600">${escape(performance.win_rate)}%</div></td></tr></tbody></table></div></div></div>`}  ${``} </div>`;
});
export {
  Page as default
};
