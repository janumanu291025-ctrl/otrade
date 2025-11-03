import { c as create_ssr_component, a as subscribe, e as escape, b as add_attribute, d as each } from "../../../../chunks/ssr.js";
import { n as notifications } from "../../../../chunks/stores2.js";
function getCategoryColor(category) {
  const colors = {
    order: "bg-blue-50 border-blue-200",
    trend: "bg-purple-50 border-purple-200",
    contract: "bg-yellow-50 border-yellow-200",
    signal: "bg-green-50 border-green-200",
    system: "bg-indigo-50 border-indigo-200",
    error: "bg-red-50 border-red-200",
    general: "bg-gray-50 border-gray-200"
  };
  return colors[category] || colors.general;
}
function getCategoryIcon(category) {
  const icons = {
    order: "📋",
    trend: "📊",
    contract: "📄",
    signal: "🔔",
    system: "⚙️",
    error: "❌",
    general: "ℹ️"
  };
  return icons[category] || icons.general;
}
function formatTimestamp(timestamp) {
  const date = new Date(timestamp);
  const now = /* @__PURE__ */ new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 6e4);
  const diffHours = Math.floor(diffMs / 36e5);
  const diffDays = Math.floor(diffMs / 864e5);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString() + " " + date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
const Page = create_ssr_component(($$result, $$props, $$bindings, slots) => {
  let $notifications, $$unsubscribe_notifications;
  $$unsubscribe_notifications = subscribe(notifications, (value) => $notifications = value);
  let filteredNotifications = [];
  let selectedCategory = "all";
  let searchQuery = "";
  const categories = [
    {
      id: "all",
      label: "All",
      color: "bg-gray-100 text-gray-700"
    },
    {
      id: "order",
      label: "Orders",
      color: "bg-blue-100 text-blue-700"
    },
    {
      id: "trend",
      label: "Trends",
      color: "bg-purple-100 text-purple-700"
    },
    {
      id: "contract",
      label: "Contracts",
      color: "bg-yellow-100 text-yellow-700"
    },
    {
      id: "signal",
      label: "Signals",
      color: "bg-green-100 text-green-700"
    },
    {
      id: "system",
      label: "System",
      color: "bg-indigo-100 text-indigo-700"
    },
    {
      id: "error",
      label: "Errors",
      color: "bg-red-100 text-red-700"
    }
  ];
  {
    {
      filteredNotifications = $notifications.filter((notif) => {
        const matchesCategory = selectedCategory === "all";
        const matchesSearch = searchQuery === "";
        return matchesCategory && matchesSearch;
      });
    }
  }
  $$unsubscribe_notifications();
  return `<div class="signals-page"> <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4"><div class="flex items-center justify-between mb-4"><h2 class="text-xl font-bold text-gray-800" data-svelte-h="svelte-uu5uio">Signal History</h2> <div class="flex items-center gap-2"><span class="text-sm text-gray-600">${escape(filteredNotifications.length)} of ${escape($notifications.length)} signals</span> <button class="px-3 py-1 text-sm bg-red-50 text-red-600 rounded hover:bg-red-100 transition-colors" ${$notifications.length === 0 ? "disabled" : ""}>Clear All</button></div></div>  <div class="mb-4"><input type="text" placeholder="Search notifications..." class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"${add_attribute("value", searchQuery, 0)}></div>  <div class="flex flex-wrap gap-2">${each(categories, (category) => {
    return `<button class="${"px-4 py-2 rounded-lg text-sm font-medium transition-all " + escape(
      selectedCategory === category.id ? category.color + " ring-2 ring-offset-2 ring-red-400" : "bg-gray-100 text-gray-600 hover:bg-gray-200",
      true
    )}">${escape(category.label)} </button>`;
  })}</div></div>  <div class="bg-white rounded-lg shadow-sm border border-gray-200">${filteredNotifications.length === 0 ? `<div class="p-8 text-center"><div class="text-4xl mb-2" data-svelte-h="svelte-1b0xkmt">🔍</div> <p class="text-gray-600">${escape("No notifications yet")}</p></div>` : `<div class="divide-y divide-gray-200">${each(filteredNotifications, (notification, index) => {
    return `<div class="${"p-4 hover:bg-gray-50 transition-colors border-l-4 " + escape(getCategoryColor(notification.category), true)}"><div class="flex items-start gap-3"> <div class="text-2xl flex-shrink-0">${escape(getCategoryIcon(notification.category))}</div>  <div class="flex-1 min-w-0"><div class="flex items-start justify-between gap-2"><p class="text-gray-800 text-sm">${escape(notification.message)}</p> <span class="text-xs text-gray-500 whitespace-nowrap">${escape(formatTimestamp(notification.timestamp))} </span></div>  <div class="mt-2"><span class="${"inline-flex items-center px-2 py-1 rounded text-xs font-medium " + escape(categories.find((c) => c.id === notification.category)?.color || "bg-gray-100 text-gray-700", true)}">${escape(notification.category)} </span></div> </div></div> </div>`;
  })}</div>`}</div>  ${filteredNotifications.length >= 50 ? `<div class="mt-4 text-center" data-svelte-h="svelte-xfppyp"><button class="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">Load More</button></div>` : ``}</div>`;
});
export {
  Page as default
};
