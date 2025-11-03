import { c as create_ssr_component, o as onDestroy, e as escape, d as each, b as add_attribute } from "../../../chunks/ssr.js";
import "../../../chunks/api.js";
function formatCurrency(value) {
  return new Intl.NumberFormat(
    "en-IN",
    {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2
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
    realized_pnl: 0,
    unrealized_pnl: 0,
    total_pnl: 0,
    win_rate: 0
  };
  let configs = [];
  let enableHistoricalMode = false;
  onDestroy(() => {
  });
  return `<div class="space-y-6"> <div class="flex justify-between items-center"><div data-svelte-h="svelte-km6g7k"><h1 class="text-3xl font-bold text-gray-900">Paper Trade</h1> <p class="text-gray-600 mt-1">Real-time paper trade with live market data</p></div> <div class="flex items-center gap-3"> ${``}  <div class="${"px-4 py-2 rounded-lg " + escape(getStatusColor(engineStatus.status), true) + " font-semibold"}">${escape(engineStatus.status.toUpperCase())}</div></div></div>  <div class="border-b border-gray-200"><div class="flex gap-1 p-2"><button class="${"px-6 py-3 rounded-t-lg font-medium transition-colors " + escape(
    "bg-blue-600 text-white",
    true
  )}">🏠 Dashboard</button> <button class="${"px-6 py-3 rounded-t-lg font-medium transition-colors " + escape(
    "text-gray-600 hover:bg-gray-100",
    true
  )}">📊 Trades</button></div></div>  ${``}  ${`<div class="grid grid-cols-1 lg:grid-cols-3 gap-6"> <div class="bg-white rounded-lg shadow-md p-6"><h2 class="text-xl font-bold mb-4" data-svelte-h="svelte-1mjetow">Controls</h2> <div class="mb-4"><label for="config-select" class="block text-sm font-medium text-gray-700 mb-2" data-svelte-h="svelte-bdv5vt">Configuration</label> <select id="config-select" ${""} class="w-full px-4 py-2 border rounded-lg disabled:bg-gray-100">${each(configs, (config) => {
    return `<option${add_attribute("value", config.id, 0)}>${escape(config.name)}</option>`;
  })}</select> <p class="text-xs text-gray-600 mt-2" data-svelte-h="svelte-pzt8x3">Manage configurations on the <a href="/config" class="text-blue-600 hover:underline font-semibold">Configuration</a> page.</p></div>  ${`<div class="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200"><label class="flex items-start gap-3 cursor-pointer"><input type="checkbox" ${""} class="w-5 h-5 mt-0.5"${add_attribute("checked", enableHistoricalMode, 1)}> <div class="flex-1"><span class="text-sm font-medium text-gray-900" data-svelte-h="svelte-x0okoj">Enable Historical Simulation</span> <p class="text-xs text-gray-600 mt-1">${`Replay historical market data for practice (Market is closed)`}</p> ${``}</div></label>  ${``}</div>`} <div class="space-y-2">${`<button ${"disabled"} class="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 font-semibold">▶ Start Trading</button>`} ${``}</div> ${``}</div>  <div class="lg:col-span-2 bg-white rounded-lg shadow-md p-6"><div class="flex justify-between items-center mb-4"><h2 class="text-xl font-bold">Market Data
						${``}</h2> <div class="${"text-sm font-medium " + escape(
    "text-gray-500",
    true
  )}">${escape("🔴 Market Closed")}</div></div> <div class="grid grid-cols-1 gap-4"> <div class="bg-blue-50 rounded-lg p-4"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-hf8bux">NIFTY 50 LTP</div> <div class="text-2xl font-bold">${escape("-")}</div></div>  <div class="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200"><div class="text-sm font-semibold text-purple-900 mb-3">Major Trend (${escape(engineStatus.major_timeframe)})</div> <div class="grid grid-cols-2 gap-3"><div><div class="text-xs text-purple-700 mb-1" data-svelte-h="svelte-1o115vw">Trend Status</div> <div class="${"text-lg font-bold " + escape(getTrendColor(), true)}">${escape("-")}</div></div> <div><div class="text-xs text-purple-700 mb-1" data-svelte-h="svelte-1tm194n">Last Changed</div> <div class="text-sm font-medium text-purple-900">${escape("-")}</div></div> <div><div class="text-xs text-purple-700 mb-1" data-svelte-h="svelte-2d4e72">7 MA</div> <div class="text-sm font-bold text-purple-900">${escape("-")}</div></div> <div><div class="text-xs text-purple-700 mb-1" data-svelte-h="svelte-1hkj361">20 MA</div> <div class="text-sm font-bold text-purple-900">${escape("-")}</div></div></div></div>  <div class="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200"><div class="text-sm font-semibold text-green-900 mb-3">Minor Trend (${escape(engineStatus.minor_timeframe)})</div> <div class="grid grid-cols-2 gap-3"><div><div class="text-xs text-green-700 mb-1" data-svelte-h="svelte-f44lij">Trend Status</div> <div class="${"text-lg font-bold " + escape(getTrendColor(), true)}">${escape("-")}</div></div> <div><div class="text-xs text-green-700 mb-1" data-svelte-h="svelte-n05me2">Last Changed</div> <div class="text-sm font-medium text-green-900">${escape("-")}</div></div> <div><div class="text-xs text-green-700 mb-1" data-svelte-h="svelte-nl7vkh">7 MA</div> <div class="text-sm font-bold text-green-900">${escape("-")}</div></div> <div><div class="text-xs text-green-700 mb-1" data-svelte-h="svelte-saskzk">20 MA</div> <div class="text-sm font-bold text-green-900">${escape("-")}</div></div></div></div>  <div class="bg-purple-50 rounded-lg p-4"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-15didq4">Active Positions</div> <div class="text-2xl font-bold text-purple-600">${escape(0)}</div></div></div></div></div>  <div class="bg-white rounded-lg shadow-md p-6"><h2 class="text-xl font-bold mb-4" data-svelte-h="svelte-2m5op8">Performance</h2> <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4"><div class="bg-gray-50 rounded-lg p-4"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-1cqie0c">Initial Capital</div> <div class="text-lg font-bold">${escape(formatCurrency(engineStatus.initial_capital))}</div></div> <div class="bg-blue-50 rounded-lg p-4"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-orciir">Current Capital</div> <div class="text-lg font-bold text-blue-600">${escape(formatCurrency(engineStatus.current_capital))}</div></div> <div class="bg-purple-50 rounded-lg p-4"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-1btd1ev">Total Trades</div> <div class="text-lg font-bold text-purple-600">${escape(performance.total_trades)}</div></div> <div class="bg-gray-50 rounded-lg p-4"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-10n7ux2">Realized P&amp;L</div> <div class="${"text-lg font-bold " + escape(getPnLColor(), true)}">${escape(formatCurrency(performance.realized_pnl))}</div></div> <div class="bg-gray-50 rounded-lg p-4"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-1u7d9cd">Unrealized P&amp;L</div> <div class="${"text-lg font-bold " + escape(getPnLColor(), true)}">${escape(formatCurrency(performance.unrealized_pnl))}</div></div> <div class="bg-gray-50 rounded-lg p-4"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-15zx8ok">Total P&amp;L</div> <div class="${"text-lg font-bold " + escape(getPnLColor(), true)}">${escape(formatCurrency(performance.total_pnl))}</div></div> <div class="bg-gray-50 rounded-lg p-4"><div class="text-sm text-gray-600 mb-1" data-svelte-h="svelte-1o6kdim">Win Rate</div> <div class="text-lg font-bold text-gray-900">${escape(performance.win_rate)}%</div></div></div></div>`}  ${``} </div>`;
});
export {
  Page as default
};
