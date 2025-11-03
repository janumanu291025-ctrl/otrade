import { c as create_ssr_component, a as subscribe, o as onDestroy, b as add_attribute, e as escape, d as each } from "../../chunks/ssr.js";
import { b as broker } from "../../chunks/broker.js";
import "../../chunks/api.js";
function formatDate(dateStr) {
  const date = /* @__PURE__ */ new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-IN", {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric"
  });
}
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $broker, $$unsubscribe_broker;
  $$unsubscribe_broker = subscribe(broker, (value) => $broker = value);
  let brokerStatus = {
    connected: false,
    broker_type: "kite",
    token_expired: false
  };
  let brokerConfig = {
    api_key: "",
    api_secret: "",
    redirect_url: "",
    postback_url: ""
  };
  let marketHours = {
    start_time: "09:15",
    end_time: "15:30",
    trading_days: [0, 1, 2, 3, 4],
    webhook_url: "",
    polling_interval_seconds: 300
  };
  let holidays = [];
  let selectedYear = (/* @__PURE__ */ new Date()).getFullYear();
  const dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  onDestroy(() => {
  });
  {
    if ($broker) {
      brokerStatus.connected = $broker.connected;
      brokerStatus.broker_type = $broker.brokerType;
      brokerStatus.token_expired = $broker.tokenExpired || false;
    }
  }
  $$unsubscribe_broker();
  return ` <div class="px-8 py-6"> <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6"> <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"><h2 class="text-xl font-bold mb-4 text-gray-900 flex items-center gap-2">Kite Connect Configuration
							<div class="${"w-4 h-4 rounded-full " + escape(brokerStatus.connected ? "bg-green-500" : "bg-red-500", true)}"></div></h2> ${``} ${``} <form class="space-y-4"><div><label for="api-key" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-14vmx18">API Key *</label> <input id="api-key" type="text" required placeholder="Enter your Kite API Key" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", brokerConfig.api_key, 0)}> <p class="text-xs text-gray-600 mt-1" data-svelte-h="svelte-5xi9v0">Get your API key from <a href="https://kite.trade/" target="_blank" class="text-blue-600 hover:underline">kite.trade</a></p></div> <div><label for="api-secret" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-q7faeu">API Secret *</label> <div class="relative">${`<input id="api-secret" type="password" required placeholder="Enter your Kite API Secret" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-10"${add_attribute("value", brokerConfig.api_secret, 0)}>`} <button type="button" class="absolute right-3 top-3 text-gray-600 hover:text-gray-900">${escape("👁️")}</button></div></div> <div><label for="redirect-url" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-skvl48">Redirect URL</label> <input id="redirect-url" type="text" placeholder="https://your-domain.com/api/broker/callback" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", brokerConfig.redirect_url, 0)}></div> <div><label for="postback-url" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-1jomirl">Postback URL (Optional)</label> <input id="postback-url" type="text" placeholder="https://your-domain.com/api/broker/postback" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", brokerConfig.postback_url, 0)}></div> <div class="flex gap-3 pt-4"><button type="submit" ${""} class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 w-32">${escape("Save")}</button> <button type="button" ${!brokerStatus.connected && true ? "disabled" : ""} class="${"px-6 py-2 " + escape(
    brokerStatus.connected ? "bg-red-600 hover:bg-red-700" : "bg-green-600 hover:bg-green-700",
    true
  ) + " text-white rounded-lg disabled:opacity-50 w-32"}">${escape(brokerStatus.connected ? "Disconnect" : "Connect Broker")}</button></div></form></div> <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"><h2 class="text-xl font-bold mb-4 text-gray-900" data-svelte-h="svelte-ka9akk">Market Hours Configuration</h2> ${``} ${``} <form class="space-y-6"> <div class="grid grid-cols-2 gap-4"><div><label for="market-open-time" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-1ym1keb">Market Open Time</label> <input id="market-open-time" type="time" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", marketHours.start_time, 0)}></div> <div><label for="market-close-time" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-40wiyx">Market Close Time</label> <input id="market-close-time" type="time" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", marketHours.end_time, 0)}></div></div>  <div><div class="block text-sm font-medium text-gray-700 mb-2" data-svelte-h="svelte-8grmb8">Trading Days</div> <div class="flex flex-wrap gap-2">${each(dayNames, (day, index) => {
    return `<button type="button" class="${"px-4 py-2 rounded-lg text-sm font-medium transition-colors " + escape(
      marketHours.trading_days.includes(index) ? "bg-blue-600 text-white hover:bg-blue-700" : "bg-gray-100 text-gray-700 hover:bg-gray-200",
      true
    )}">${escape(day)} </button>`;
  })}</div></div>  <div class="border-t pt-6"><div class="mb-3" data-svelte-h="svelte-1x3wa33"><div class="font-medium text-gray-900">Real-time Updates (Webhook)</div> <p class="text-sm text-gray-600">Webhook is automatically enabled during market hours for instant order updates</p></div> <label for="webhook-url" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-1qv9jgd">Webhook URL (Optional)</label> <input id="webhook-url" type="text" placeholder="https://your-domain.com/api/webhook/kite-postback" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", marketHours.webhook_url, 0)}></div>  <div class="border-t pt-6"><div class="mb-3" data-svelte-h="svelte-t1htdh"><div class="font-medium text-gray-900">API Polling (Outside Market Hours)</div> <p class="text-sm text-gray-600">API polling is automatically enabled outside market hours to fetch order status periodically</p></div> <div><label for="polling-interval" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-118cwx4">Polling Interval (seconds)</label> <input id="polling-interval" type="number" min="60" max="3600" step="60" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", marketHours.polling_interval_seconds, 0)}> <p class="text-xs text-gray-600 mt-1" data-svelte-h="svelte-5c4xig">Minimum 60 seconds, recommended 300</p></div></div> <div class="flex gap-3 pt-4"><button type="submit" ${""} class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">${escape("Save Market Hours")}</button></div></form></div>  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"><div class="flex justify-between items-center mb-4"><h2 class="text-xl font-bold text-gray-900" data-svelte-h="svelte-tnqj9n">Holidays Management</h2> <div class="flex gap-3 items-center"><select class="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"><option${add_attribute("value", 2024, 0)} data-svelte-h="svelte-1p1p0dm">2024</option><option${add_attribute("value", 2025, 0)} data-svelte-h="svelte-1913zg6">2025</option><option${add_attribute("value", 2026, 0)} data-svelte-h="svelte-1smxaly">2026</option></select> <button class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"><span>${escape("+")}</span> ${escape("Add Holiday")}</button></div></div> ${``} ${``}  ${``}  ${`${holidays.length === 0 ? `<div class="text-center py-8 text-gray-500"><svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg> <p class="mt-2">No holidays found for ${escape(selectedYear)}</p></div>` : `<div class="space-y-2"><div class="text-sm text-gray-600 mb-2">Total: ${escape(holidays.length)} holiday${escape(holidays.length !== 1 ? "s" : "")}</div> <div class="max-h-96 overflow-y-auto">${each(holidays, (holiday) => {
    return `<div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors border border-gray-200 mb-2"><div class="flex-1"><div class="flex items-center gap-3"><div class="text-sm font-medium text-gray-500 min-w-[120px]">${escape(formatDate(holiday.date))}</div> <div class="flex-1"><div class="font-semibold text-gray-900">${escape(holiday.name)}</div> ${holiday.description ? `<div class="text-sm text-gray-600">${escape(holiday.description)}</div>` : ``}</div> </div></div> <button ${""} class="ml-4 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm" title="Delete holiday">🗑️ Delete</button> </div>`;
  })}</div></div>`}`}</div>  <div class="grid grid-cols-1 gap-6"> <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"><div class="flex items-center justify-between mb-4"><h2 class="text-lg font-bold text-gray-900 flex items-center gap-2">📥 Instrument Data
								${``}</h2> <button ${""} class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm flex items-center gap-1"><span data-svelte-h="svelte-18xxwx0">📥</span> ${escape("Download")}</button></div> ${``} ${``} ${`${``}`}</div>  ${``}</div></div></div>`;
});
export {
  Page as default
};
