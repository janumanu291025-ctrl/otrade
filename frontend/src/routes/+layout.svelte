<script>
	import '../app.css';
	import { onMount } from 'svelte';
	import { websocket } from '$lib/stores/websocket';
	import { broker } from '$lib/stores/broker';
	
	let currentPath = '';
	
	onMount(() => {
		websocket.connect();
		broker.loadStatus('kite');
		
		return () => {
			websocket.disconnect();
		};
	});
</script>

<div class="min-h-screen flex bg-gray-50">
	<!-- Sidebar -->
	<aside class="w-64 bg-white shadow-lg border-r border-gray-200">
		<div class="p-6 border-b border-gray-200">
			<div class="flex items-center gap-2">
				<h1 class="text-2xl font-bold text-blue-600">OTrade</h1>
				<div class="w-3 h-3 rounded-full {$broker.connected ? 'bg-green-500' : 'bg-red-500'}"></div>
			</div>
		</div>
		
		<nav class="p-4 space-y-1">
			<a href="/" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150">
				<span class="text-xl">🏠</span>
				<span class="font-medium">Home</span>
			</a>
			<a href="/config" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150">
				<span class="text-xl">⚙️</span>
				<span class="font-medium">Config</span>
			</a>
		<a href="/paper-trading" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150">
			<span class="text-xl">📄</span>
			<span class="font-medium">Mock</span>
		</a>
		<a href="/live-trading-v2" class="flex items-center gap-3 px-4 py-3 rounded-lg text-red-700 hover:bg-red-50 hover:text-red-600 transition-colors duration-150 font-semibold">
			<span class="text-xl">🔴</span>
			<span class="font-medium">Live</span>
		</a>
		<a href="/graph" class="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors duration-150">
			<span class="text-xl">�</span>
			<span class="font-medium">Graph</span>
		</a>
		</nav>
	</aside>
	
	<!-- Main Content -->
	<main class="flex-1 overflow-auto">
		<div class="p-8">
			<slot />
		</div>
	</main>
</div>
