<script>
	import { createEventDispatcher } from 'svelte';
	import { engineStatus, configs } from '../stores.js';
	
	const dispatch = createEventDispatcher();
	
	let selectedConfigId = null;
	let contractExpiry = '';
	let showStartForm = false;
	
	function handleStart() {
		if (!selectedConfigId) {
			alert('Please select a trading configuration');
			return;
		}
		
		dispatch('start', {
			configId: selectedConfigId,
			contractExpiry: contractExpiry || null
		});
		
		showStartForm = false;
	}
	
	function handleStop() {
		dispatch('stop');
	}
	
	function handlePause() {
		dispatch('pause');
	}
	
	function handleResume() {
		dispatch('resume');
	}
</script>

<div class="bg-white rounded-lg shadow p-6">
	<div class="flex items-center justify-between">
		<h2 class="text-lg font-semibold text-gray-900">Trading Controls</h2>
		
		<div class="flex gap-3">
			{#if !$engineStatus.running}
				<!-- Start Form -->
				{#if showStartForm}
					<div class="flex items-center gap-3">
						<select
							bind:value={selectedConfigId}
							class="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
						>
							<option value={null}>Select Config</option>
							{#each $configs as config}
								<option value={config.id}>{config.name}</option>
							{/each}
						</select>
						
						<input
							type="text"
							bind:value={contractExpiry}
							placeholder="Expiry (YYMMDD)"
							class="border border-gray-300 rounded-md px-3 py-2 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-blue-500"
						/>
						
						<button
							on:click={handleStart}
							class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
						>
							Start
						</button>
						
						<button
							on:click={() => showStartForm = false}
							class="bg-gray-300 hover:bg-gray-400 text-gray-700 px-4 py-2 rounded-md text-sm font-medium transition-colors"
						>
							Cancel
						</button>
					</div>
				{:else}
					<button
						on:click={() => showStartForm = true}
						class="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-md text-sm font-medium transition-colors"
					>
						🚀 Start Trading
					</button>
				{/if}
			{:else}
				<!-- Running Controls -->
				{#if $engineStatus.paused}
					<button
						on:click={handleResume}
						class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-md text-sm font-medium transition-colors"
					>
						▶️ Resume
					</button>
				{:else}
					<button
						on:click={handlePause}
						class="bg-yellow-600 hover:bg-yellow-700 text-white px-6 py-2 rounded-md text-sm font-medium transition-colors"
					>
						⏸️ Pause
					</button>
				{/if}
				
				<button
					on:click={handleStop}
					class="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-md text-sm font-medium transition-colors"
				>
					⏹️ Stop
				</button>
			{/if}
		</div>
	</div>
</div>
