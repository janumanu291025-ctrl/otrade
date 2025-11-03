import { c as create_ssr_component, a as subscribe, d as each, e as escape } from "../../../../chunks/ssr.js";
import { s as statistics } from "../../../../chunks/stores2.js";
function formatCurrency(value) {
  return new Intl.NumberFormat(
    "en-IN",
    {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }
  ).format(value);
}
function formatPercentage(value) {
  return `${value.toFixed(2)}%`;
}
function getColorClass(value) {
  if (value > 0) return "text-green-600";
  if (value < 0) return "text-red-600";
  return "text-gray-600";
}
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let performanceMetrics;
  let $statistics, $$unsubscribe_statistics;
  $$unsubscribe_statistics = subscribe(statistics, (value) => $statistics = value);
  let selectedPeriod = "1d";
  const periods = [
    { id: "1d", label: "Today" },
    { id: "1w", label: "1 Week" },
    { id: "1m", label: "1 Month" },
    { id: "3m", label: "3 Months" },
    { id: "all", label: "All Time" }
  ];
  performanceMetrics = {
    totalPnL: $statistics?.total_pnl || 0,
    unrealizedPnL: $statistics?.unrealized_pnl || 0,
    realizedPnL: ($statistics?.total_pnl || 0) - ($statistics?.unrealized_pnl || 0),
    winRate: $statistics?.win_rate || 0,
    totalTrades: $statistics?.total_trades || 0,
    winningTrades: Math.round(($statistics?.total_trades || 0) * ($statistics?.win_rate || 0) / 100),
    losingTrades: ($statistics?.total_trades || 0) - Math.round(($statistics?.total_trades || 0) * ($statistics?.win_rate || 0) / 100),
    ceTrades: $statistics?.ce_trades || 0,
    peTrades: $statistics?.pe_trades || 0,
    avgWinAmount: 0,
    avgLossAmount: 0,
    largestWin: 0,
    largestLoss: 0,
    profitFactor: 0,
    sharpeRatio: 0
  };
  {
    {
      if (performanceMetrics.winningTrades > 0) {
        performanceMetrics.avgWinAmount = performanceMetrics.realizedPnL / performanceMetrics.winningTrades;
      }
      if (performanceMetrics.losingTrades > 0) {
        performanceMetrics.avgLossAmount = Math.abs(performanceMetrics.realizedPnL) / performanceMetrics.losingTrades;
      }
    }
  }
  $$unsubscribe_statistics();
  return `<div class="analytics-page space-y-4"> <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><div class="flex items-center justify-between"><h2 class="text-xl font-bold text-gray-800" data-svelte-h="svelte-tfo0gy">Performance Analytics</h2> <div class="flex gap-2">${each(periods, (period) => {
    return `<button class="${"px-4 py-2 rounded-lg text-sm font-medium transition-all " + escape(
      selectedPeriod === period.id ? "bg-red-100 text-red-700 ring-2 ring-red-400" : "bg-gray-100 text-gray-600 hover:bg-gray-200",
      true
    )}">${escape(period.label)} </button>`;
  })}</div></div></div>  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"> <div class="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg shadow-sm border border-blue-200 p-4"><div class="text-sm text-blue-700 font-medium mb-1" data-svelte-h="svelte-1m24sr9">Total P&amp;L</div> <div class="${"text-2xl font-bold " + escape(getColorClass(performanceMetrics.totalPnL), true)}">${escape(formatCurrency(performanceMetrics.totalPnL))}</div> <div class="text-xs text-blue-600 mt-1">Realized: ${escape(formatCurrency(performanceMetrics.realizedPnL))}</div></div>  <div class="bg-gradient-to-br from-green-50 to-green-100 rounded-lg shadow-sm border border-green-200 p-4"><div class="text-sm text-green-700 font-medium mb-1" data-svelte-h="svelte-115ensa">Win Rate</div> <div class="text-2xl font-bold text-green-600">${escape(formatPercentage(performanceMetrics.winRate))}</div> <div class="text-xs text-green-600 mt-1">${escape(performanceMetrics.winningTrades)}W / ${escape(performanceMetrics.losingTrades)}L</div></div>  <div class="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg shadow-sm border border-purple-200 p-4"><div class="text-sm text-purple-700 font-medium mb-1" data-svelte-h="svelte-1grv9rc">Total Trades</div> <div class="text-2xl font-bold text-purple-600">${escape(performanceMetrics.totalTrades)}</div> <div class="text-xs text-purple-600 mt-1">CE: ${escape(performanceMetrics.ceTrades)} | PE: ${escape(performanceMetrics.peTrades)}</div></div>  <div class="bg-gradient-to-br from-yellow-50 to-yellow-100 rounded-lg shadow-sm border border-yellow-200 p-4"><div class="text-sm text-yellow-700 font-medium mb-1" data-svelte-h="svelte-vhfsfj">Avg Win/Loss</div> <div class="text-lg font-bold text-green-600">${escape(formatCurrency(performanceMetrics.avgWinAmount))}</div> <div class="text-lg font-bold text-red-600">${escape(formatCurrency(performanceMetrics.avgLossAmount))}</div></div></div>  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4"> <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><h3 class="text-lg font-bold text-gray-800 mb-4" data-svelte-h="svelte-1g6jm3w">Trade Statistics</h3> <div class="space-y-3"><div class="flex justify-between items-center"><span class="text-sm text-gray-600" data-svelte-h="svelte-1r4r3g2">Winning Trades</span> <span class="font-semibold text-green-600">${escape(performanceMetrics.winningTrades)}</span></div> <div class="flex justify-between items-center"><span class="text-sm text-gray-600" data-svelte-h="svelte-1h5wim">Losing Trades</span> <span class="font-semibold text-red-600">${escape(performanceMetrics.losingTrades)}</span></div> <div class="flex justify-between items-center"><span class="text-sm text-gray-600" data-svelte-h="svelte-45nh8t">Win Rate</span> <span class="font-semibold text-gray-800">${escape(formatPercentage(performanceMetrics.winRate))}</span></div> <div class="flex justify-between items-center pt-3 border-t border-gray-200"><span class="text-sm text-gray-600" data-svelte-h="svelte-p5w0lg">CE Trades</span> <span class="font-semibold text-blue-600">${escape(performanceMetrics.ceTrades)}</span></div> <div class="flex justify-between items-center"><span class="text-sm text-gray-600" data-svelte-h="svelte-be8lc3">PE Trades</span> <span class="font-semibold text-purple-600">${escape(performanceMetrics.peTrades)}</span></div></div></div>  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><h3 class="text-lg font-bold text-gray-800 mb-4" data-svelte-h="svelte-63d3r0">P&amp;L Breakdown</h3> <div class="space-y-3"><div class="flex justify-between items-center"><span class="text-sm text-gray-600" data-svelte-h="svelte-114ki1d">Total P&amp;L</span> <span class="${"font-semibold " + escape(getColorClass(performanceMetrics.totalPnL), true)}">${escape(formatCurrency(performanceMetrics.totalPnL))}</span></div> <div class="flex justify-between items-center"><span class="text-sm text-gray-600" data-svelte-h="svelte-1961esh">Realized P&amp;L</span> <span class="${"font-semibold " + escape(getColorClass(performanceMetrics.realizedPnL), true)}">${escape(formatCurrency(performanceMetrics.realizedPnL))}</span></div> <div class="flex justify-between items-center"><span class="text-sm text-gray-600" data-svelte-h="svelte-12nmcya">Unrealized P&amp;L</span> <span class="${"font-semibold " + escape(getColorClass(performanceMetrics.unrealizedPnL), true)}">${escape(formatCurrency(performanceMetrics.unrealizedPnL))}</span></div> <div class="flex justify-between items-center pt-3 border-t border-gray-200"><span class="text-sm text-gray-600" data-svelte-h="svelte-ulpk6v">Avg Win Amount</span> <span class="font-semibold text-green-600">${escape(formatCurrency(performanceMetrics.avgWinAmount))}</span></div> <div class="flex justify-between items-center"><span class="text-sm text-gray-600" data-svelte-h="svelte-2pevxm">Avg Loss Amount</span> <span class="font-semibold text-red-600">${escape(formatCurrency(performanceMetrics.avgLossAmount))}</span></div></div></div></div>  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4" data-svelte-h="svelte-17ejyou"><h3 class="text-lg font-bold text-gray-800 mb-4">P&amp;L Over Time</h3> <div class="h-64 flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200"><div class="text-center"><div class="text-4xl mb-2">📈</div> <p class="text-gray-600">Chart visualization coming soon</p> <p class="text-sm text-gray-500 mt-1">Will display P&amp;L trend over selected period</p></div></div></div>  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4" data-svelte-h="svelte-157ql4m"><div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><h3 class="text-lg font-bold text-gray-800 mb-4">Win/Loss Distribution</h3> <div class="h-48 flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200"><div class="text-center"><div class="text-4xl mb-2">📊</div> <p class="text-gray-600">Pie chart coming soon</p></div></div></div> <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"><h3 class="text-lg font-bold text-gray-800 mb-4">CE vs PE Performance</h3> <div class="h-48 flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200"><div class="text-center"><div class="text-4xl mb-2">📊</div> <p class="text-gray-600">Bar chart coming soon</p></div></div></div></div></div>`;
});
export {
  Page as default
};
