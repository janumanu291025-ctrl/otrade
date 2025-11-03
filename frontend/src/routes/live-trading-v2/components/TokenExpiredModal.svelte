<script>
	import { createEventDispatcher } from 'svelte';
	import { showTokenExpiredModal } from '../stores.js';
	
	const dispatch = createEventDispatcher();
	
	function handleReauth() {
		dispatch('reauth');
		showTokenExpiredModal.set(false);
	}
	
	function handleClose() {
		showTokenExpiredModal.set(false);
	}
</script>

{#if $showTokenExpiredModal}
	<div class="fixed inset-0 z-50 overflow-y-auto">
		<!-- Backdrop -->
		<div
			class="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
			on:click={handleClose}
			on:keydown={(e) => e.key === 'Escape' && handleClose()}
			role="button"
			tabindex="-1"
		></div>
		
		<!-- Modal -->
		<div class="flex min-h-full items-center justify-center p-4">
			<div class="relative bg-white rounded-lg shadow-xl max-w-md w-full">
				<!-- Header -->
				<div class="bg-red-600 text-white px-6 py-4 rounded-t-lg">
					<div class="flex items-center gap-3">
						<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
						</svg>
						<h3 class="text-xl font-semibold">Session Expired</h3>
					</div>
				</div>
				
				<!-- Body -->
				<div class="px-6 py-6">
					<div class="space-y-4">
						<p class="text-gray-700">
							Your broker authentication token has expired. The trading engine has been paused to prevent errors.
						</p>
						
						<div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
							<div class="flex gap-3">
								<svg class="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
								<div class="text-sm text-yellow-800">
									<p class="font-medium mb-1">What happens now?</p>
									<ul class="list-disc list-inside space-y-1">
										<li>Trading engine is paused</li>
										<li>No new positions will be opened</li>
										<li>Existing positions remain open</li>
										<li>Re-authenticate to resume trading</li>
									</ul>
								</div>
							</div>
						</div>
						
						<div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
							<div class="flex gap-3">
								<svg class="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
								<div class="text-sm text-blue-800">
									<p class="font-medium mb-1">To continue trading:</p>
									<ol class="list-decimal list-inside space-y-1">
										<li>Click "Re-authenticate" below</li>
										<li>Complete broker login process</li>
										<li>Resume trading from dashboard</li>
									</ol>
								</div>
							</div>
						</div>
					</div>
				</div>
				
				<!-- Footer -->
				<div class="px-6 py-4 bg-gray-50 rounded-b-lg flex justify-end gap-3">
					<button
						on:click={handleClose}
						class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
					>
						Dismiss
					</button>
					<button
						on:click={handleReauth}
						class="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
					>
						Re-authenticate
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
