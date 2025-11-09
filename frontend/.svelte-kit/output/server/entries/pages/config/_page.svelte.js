import { c as create_ssr_component, f as each, e as escape } from "../../../chunks/ssr.js";
import "../../../chunks/api.js";
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let configs = [];
  return `<div class="container mx-auto p-6">${``}  ${``}  <div class="bg-white rounded-lg shadow-lg p-6"><div class="flex justify-between items-center mb-4"><h2 class="text-2xl font-bold" data-svelte-h="svelte-143k4ty">All Configurations</h2> <button class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition" ${""}>New Configuration</button></div> ${`${configs.length === 0 ? `<div class="text-center py-8 text-gray-500" data-svelte-h="svelte-1u0u649">No configurations found. Create your first configuration to get started.</div>` : `<div class="grid grid-cols-3 gap-4">${each(configs, (config) => {
    return `<div class="${"border rounded-lg p-4 " + escape(
      config.is_active ? "border-green-500 bg-green-50" : "border-gray-200",
      true
    )}"><div class="flex items-start justify-between mb-2"><div class="flex-1"><div class="flex items-center justify-between"><h3 class="font-semibold text-lg flex items-center">${escape(config.name)} ${config.is_active ? `<span class="w-2 h-2 bg-green-500 rounded-full ml-2"></span>` : ``}</h3> <div class="flex space-x-2">${!config.is_active ? `<button class="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition" ${""}>Activate
											</button>` : ``} <button class="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition" ${""}>Edit</button> <button class="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 transition" ${""}>Delete</button> </div></div> ${config.description ? `<p class="text-sm text-gray-600 mt-1">${escape(config.description)}</p>` : ``} </div></div> </div>`;
  })}</div>`}`}</div> </div>`;
});
export {
  Page as default
};
