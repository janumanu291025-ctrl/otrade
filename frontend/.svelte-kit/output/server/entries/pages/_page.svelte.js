import { c as create_ssr_component, a as subscribe, o as onDestroy, b as add_attribute, e as escape } from "../../chunks/ssr.js";
import { b as broker } from "../../chunks/broker.js";
import "../../chunks/api.js";
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
  return ` <div class="px-8 py-6"> <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6"> <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"><h2 class="text-xl font-bold mb-4 text-gray-900 flex items-center gap-2">Kite Connect Configuration
							<div class="${"w-4 h-4 rounded-full " + escape(brokerStatus.connected ? "bg-green-500" : "bg-red-500", true)}"></div></h2> ${``} ${``} <form class="space-y-4"><div><label for="api-key" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-14vmx18">API Key *</label> <input id="api-key" type="text" required placeholder="Enter your Kite API Key" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", brokerConfig.api_key, 0)}> <p class="text-xs text-gray-600 mt-1" data-svelte-h="svelte-5xi9v0">Get your API key from <a href="https://kite.trade/" target="_blank" class="text-blue-600 hover:underline">kite.trade</a></p></div> <div><label for="api-secret" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-q7faeu">API Secret *</label> <div class="relative">${`<input id="api-secret" type="password" required placeholder="Enter your Kite API Secret" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-10"${add_attribute("value", brokerConfig.api_secret, 0)}>`} <button type="button" class="absolute right-3 top-3 text-gray-600 hover:text-gray-900">${escape("👁️")}</button></div></div> <div><label for="redirect-url" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-skvl48">Redirect URL</label> <input id="redirect-url" type="text" placeholder="https://your-domain.com/api/broker/callback" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", brokerConfig.redirect_url, 0)}></div> <div><label for="postback-url" class="block text-sm font-medium text-gray-700 mb-1" data-svelte-h="svelte-1jomirl">Postback URL (Optional)</label> <input id="postback-url" type="text" placeholder="https://your-domain.com/api/broker/postback" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"${add_attribute("value", brokerConfig.postback_url, 0)}></div> <div class="flex gap-3 pt-4"><button type="submit" ${""} class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 w-32">${escape("Save")}</button> <button type="button" ${!brokerStatus.connected && true ? "disabled" : ""} class="${"px-6 py-2 " + escape(
    brokerStatus.connected ? "bg-red-600 hover:bg-red-700" : "bg-green-600 hover:bg-green-700",
    true
  ) + " text-white rounded-lg disabled:opacity-50 w-32"}">${escape(brokerStatus.connected ? "Disconnect" : "Connect Broker")}</button></div></form></div>  <div class="grid grid-cols-1 gap-6"> <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"><div class="flex items-center justify-between mb-4"><h2 class="text-lg font-bold text-gray-900 flex items-center gap-2">📥 Instrument Data
								${``}</h2> <button ${""} class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm flex items-center gap-1"><span data-svelte-h="svelte-18xxwx0">📥</span> ${escape("Download")}</button></div> ${``} ${``} ${`${``}`}</div>  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"><h2 class="text-lg font-bold text-gray-900 mb-4" data-svelte-h="svelte-7229p3">🏖️ Holiday</h2> ${`${`<div class="text-center py-8" data-svelte-h="svelte-1byq5p6"><p class="text-gray-500">Loading market data...</p></div>`}`}</div>  ${``}</div></div></div>`;
});
export {
  Page as default
};
