<script>
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	
	let auth = '';
	let broker = '';
	let message = '';
	let loading = true;
	
	onMount(() => {
		// Get query parameters
		const params = $page.url.searchParams;
		auth = params.get('auth') || '';
		broker = params.get('broker') || '';
		message = params.get('message') || '';
		
		loading = false;
		
		// Close popup immediately on success
		if (auth === 'success') {
			window.close();
		}
	});
	
	function closeWindow() {
		window.close();
	}
</script>

<div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
	<div class="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full mx-4">
		{#if loading}
			<div class="text-center">
				<div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
				<p class="mt-4 text-gray-600">Processing authentication...</p>
			</div>
		{:else if auth === 'success'}
			<div class="text-center">
				<div class="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-4">
					<svg class="h-10 w-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
					</svg>
				</div>
				<h2 class="text-2xl font-bold text-gray-900 mb-2">Authentication Successful!</h2>
				<p class="text-gray-600 mb-6">
					Your {broker.toUpperCase()} broker has been successfully authenticated.
				</p>
				<button
					on:click={closeWindow}
					class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-lg transition-colors duration-150 shadow-md"
				>
					Close Now
				</button>
			</div>
		{:else if auth === 'error'}
			<div class="text-center">
				<div class="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-red-100 mb-4">
					<svg class="h-10 w-10 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</div>
				<h2 class="text-2xl font-bold text-gray-900 mb-2">Authentication Failed</h2>
				<p class="text-gray-600 mb-6">
					{message || 'An error occurred during authentication. Please try again.'}
				</p>
				<button
					on:click={closeWindow}
					class="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-3 px-4 rounded-lg transition-colors duration-150 shadow-md"
				>
					Close
				</button>
			</div>
		{:else}
			<div class="text-center">
				<div class="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-yellow-100 mb-4">
					<svg class="h-10 w-10 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
					</svg>
				</div>
				<h2 class="text-2xl font-bold text-gray-900 mb-2">Unknown Status</h2>
				<p class="text-gray-600 mb-6">
					Unable to determine authentication status.
				</p>
				<button
					on:click={closeWindow}
					class="w-full bg-gray-600 hover:bg-gray-700 text-white font-medium py-3 px-4 rounded-lg transition-colors duration-150 shadow-md"
				>
					Close
				</button>
			</div>
		{/if}
	</div>
</div>

<style>
	/* Additional custom styles if needed */
</style>
