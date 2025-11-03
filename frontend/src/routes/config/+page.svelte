<script>
	import { onMount } from 'svelte';
	import { configAPI } from '$lib/utils/api';
	
	// State
	let configs = [];
	let activeConfig = null;
	let selectedConfig = null;
	let loading = false;
	let error = null;
	let showForm = false;
	let isEditing = false;
	
	// Form data
	let form = {
		name: '',
		description: '',
		is_active: false,
		initial_capital: 100000,
		ma_short_period: 7,
		ma_long_period: 20,
		major_trend_timeframe: '15min',
		minor_trend_timeframe: '1min',
		buy_7ma_enabled: true,
		buy_7ma_percentage_below: 0.0,
		buy_7ma_target_percentage: 2.5,
		buy_7ma_stoploss_percentage: 15.0,
		buy_20ma_enabled: true,
		buy_20ma_percentage_below: 0.0,
		buy_20ma_target_percentage: 3.0,
		buy_20ma_stoploss_percentage: 15.0,
		buy_lbb_enabled: true,
		buy_lbb_percentage_below: 0.0,
		buy_lbb_target_percentage: 5.0,
		buy_lbb_stoploss_percentage: 15.0,
		capital_allocation_pct: 50.0,
		lot_size: 75,
		min_strike_gap: 100,
		strike_round_to: 100,
		square_off_time: '15:28',
		square_off_enabled: true,
		exclude_expiry_day_contracts: true,
		reverse_signals: false,
		lots_per_trade: 1,
		tick_size: 0.05,
		expiry_offset_days: 0
	};
	
	onMount(async () => {
		await loadConfigs();
		await loadActiveConfig();
	});
	
	async function loadConfigs() {
		loading = true;
		error = null;
		try {
			const response = await configAPI.getAll();
			configs = response.data.configs || [];
		} catch (err) {
			console.error('Error loading configs:', err);
			error = 'Failed to load configurations';
		} finally {
			loading = false;
		}
	}
	
	async function loadActiveConfig() {
		try {
			const response = await configAPI.getActive();
			activeConfig = response.data;
		} catch (err) {
			console.log('No active config found');
			activeConfig = null;
		}
	}
	
	async function selectConfig(config) {
		selectedConfig = config;
		isEditing = false;
	}
	
	function newConfig() {
		showForm = true;
		isEditing = false;
		form = {
			name: '',
			description: '',
			is_active: false,
			initial_capital: 100000,
			ma_short_period: 7,
			ma_long_period: 20,
			major_trend_timeframe: '15min',
			minor_trend_timeframe: '1min',
			buy_7ma_enabled: true,
			buy_7ma_percentage_below: 0.0,
			buy_7ma_target_percentage: 2.5,
			buy_7ma_stoploss_percentage: 15.0,
			buy_20ma_enabled: true,
			buy_20ma_percentage_below: 0.0,
			buy_20ma_target_percentage: 3.0,
			buy_20ma_stoploss_percentage: 15.0,
			buy_lbb_enabled: true,
			buy_lbb_percentage_below: 0.0,
			buy_lbb_target_percentage: 5.0,
			buy_lbb_stoploss_percentage: 15.0,
			capital_allocation_pct: 50.0,
			lot_size: 75,
			min_strike_gap: 100,
			strike_round_to: 100,
			square_off_time: '15:28',
			square_off_enabled: true,
			exclude_expiry_day_contracts: true,
			reverse_signals: false,
			lots_per_trade: 1,
			tick_size: 0.05,
			expiry_offset_days: 0
		};
	}
	
	function editConfig(config) {
		showForm = true;
		isEditing = true;
		form = { ...config };
	}
	
	async function saveConfig() {
		loading = true;
		error = null;
		try {
			if (isEditing && selectedConfig) {
				await configAPI.update(selectedConfig.id, form);
			} else {
				await configAPI.create(form);
			}
			await loadConfigs();
			await loadActiveConfig();
			showForm = false;
			selectedConfig = null;
		} catch (err) {
			console.error('Error saving config:', err);
			error = err.response?.data?.detail || 'Failed to save configuration';
		} finally {
			loading = false;
		}
	}
	
	async function activateConfig(config) {
		loading = true;
		error = null;
		try {
			await configAPI.activate(config.id);
			await loadConfigs();
			await loadActiveConfig();
			selectedConfig = null;
		} catch (err) {
			console.error('Error activating config:', err);
			error = 'Failed to activate configuration';
		} finally {
			loading = false;
		}
	}
	
	async function deleteConfig(config) {
		if (!confirm(`Are you sure you want to delete "${config.name}"?`)) return;
		
		loading = true;
		error = null;
		try {
			await configAPI.delete(config.id);
			await loadConfigs();
			await loadActiveConfig();
			if (selectedConfig?.id === config.id) {
				selectedConfig = null;
			}
		} catch (err) {
			console.error('Error deleting config:', err);
			error = err.response?.data?.detail || 'Failed to delete configuration';
		} finally {
			loading = false;
		}
	}
	
	function cancelForm() {
		showForm = false;
		isEditing = false;
		selectedConfig = null;
	}
</script>

<div class="container mx-auto p-6">
	
	{#if error}
		<div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
			{error}
		</div>
	{/if}
	
	<!-- Configuration Form -->
	{#if showForm}
		<div class="bg-white rounded-lg shadow-lg p-6 mb-6">
			<h2 class="text-2xl font-bold mb-4">{isEditing ? 'Edit Configuration' : 'New Configuration'}</h2>
			
			<form on:submit|preventDefault={saveConfig} class="space-y-6">
				<!-- Basic Info -->
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Configuration Name *</label>
						<input
							type="text"
							bind:value={form.name}
							required
							class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
							placeholder="e.g., Aggressive Strategy"
						/>
					</div>
					
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Initial Capital</label>
						<input
							type="number"
							bind:value={form.initial_capital}
							required
							min="1000"
							step="1000"
							class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
						/>
					</div>
				</div>
				
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
					<textarea
						bind:value={form.description}
						rows="2"
						class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
						placeholder="Optional description"
					></textarea>
				</div>
				
				<div>
					<label class="flex items-center space-x-2">
						<input type="checkbox" bind:checked={form.is_active} class="rounded" />
						<span class="text-sm font-medium text-gray-700">Set as Active Configuration</span>
					</label>
					<p class="text-xs text-gray-500 ml-6">Setting this as active will deactivate other configurations</p>
				</div>
				
				<!-- MA Settings -->
				<div class="border-t pt-4">
					<h3 class="text-lg font-semibold mb-3">Moving Average Settings</h3>
					<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Short MA Period</label>
							<input
								type="number"
								bind:value={form.ma_short_period}
								required
								min="1"
								class="w-full px-3 py-2 border border-gray-300 rounded-lg"
							/>
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Long MA Period</label>
							<input
								type="number"
								bind:value={form.ma_long_period}
								required
								min="1"
								class="w-full px-3 py-2 border border-gray-300 rounded-lg"
							/>
						</div>
					</div>
				</div>
				
				<!-- Timeframe Settings -->
				<div class="border-t pt-4">
					<h3 class="text-lg font-semibold mb-3">Timeframe Settings</h3>
					<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Major Trend Timeframe</label>
							<select bind:value={form.major_trend_timeframe} class="w-full px-3 py-2 border border-gray-300 rounded-lg">
								<option value="1min">1 Minute</option>
								<option value="5min">5 Minutes</option>
								<option value="15min">15 Minutes</option>
								<option value="1hour">1 Hour</option>
							</select>
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Minor Trend Timeframe</label>
							<select bind:value={form.minor_trend_timeframe} class="w-full px-3 py-2 border border-gray-300 rounded-lg">
								<option value="1min">1 Minute</option>
								<option value="5min">5 Minutes</option>
								<option value="15min">15 Minutes</option>
							</select>
						</div>
					</div>
				</div>
				
				<!-- 7MA Trigger -->
				<div class="border-t pt-4">
					<div class="flex items-center justify-between mb-3">
						<h3 class="text-lg font-semibold">7MA Trigger Settings</h3>
						<label class="flex items-center space-x-2">
							<input type="checkbox" bind:checked={form.buy_7ma_enabled} class="rounded" />
							<span class="text-sm">Enabled</span>
						</label>
					</div>
					<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Entry % Below</label>
							<input type="number" bind:value={form.buy_7ma_percentage_below} step="0.1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Target %</label>
							<input type="number" bind:value={form.buy_7ma_target_percentage} step="0.1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Stop Loss %</label>
							<input type="number" bind:value={form.buy_7ma_stoploss_percentage} step="0.1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
					</div>
				</div>
				
				<!-- 20MA Trigger -->
				<div class="border-t pt-4">
					<div class="flex items-center justify-between mb-3">
						<h3 class="text-lg font-semibold">20MA Trigger Settings</h3>
						<label class="flex items-center space-x-2">
							<input type="checkbox" bind:checked={form.buy_20ma_enabled} class="rounded" />
							<span class="text-sm">Enabled</span>
						</label>
					</div>
					<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Entry % Below</label>
							<input type="number" bind:value={form.buy_20ma_percentage_below} step="0.1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Target %</label>
							<input type="number" bind:value={form.buy_20ma_target_percentage} step="0.1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Stop Loss %</label>
							<input type="number" bind:value={form.buy_20ma_stoploss_percentage} step="0.1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
					</div>
				</div>
				
				<!-- LBB Trigger -->
				<div class="border-t pt-4">
					<div class="flex items-center justify-between mb-3">
						<h3 class="text-lg font-semibold">Lower Bollinger Band Trigger</h3>
						<label class="flex items-center space-x-2">
							<input type="checkbox" bind:checked={form.buy_lbb_enabled} class="rounded" />
							<span class="text-sm">Enabled</span>
						</label>
					</div>
					<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Entry % Below</label>
							<input type="number" bind:value={form.buy_lbb_percentage_below} step="0.1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Target %</label>
							<input type="number" bind:value={form.buy_lbb_target_percentage} step="0.1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Stop Loss %</label>
							<input type="number" bind:value={form.buy_lbb_stoploss_percentage} step="0.1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
					</div>
				</div>
				
				<!-- Position Sizing -->
				<div class="border-t pt-4">
					<h3 class="text-lg font-semibold mb-3">Position Sizing</h3>
					<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Capital Allocation %</label>
							<input type="number" bind:value={form.capital_allocation_pct} step="1" min="1" max="100" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Lot Size</label>
							<input type="number" bind:value={form.lot_size} min="1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Lots Per Trade (Backtest)</label>
							<input type="number" bind:value={form.lots_per_trade} min="1" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
					</div>
				</div>
				
				<!-- Strike Selection -->
				<div class="border-t pt-4">
					<h3 class="text-lg font-semibold mb-3">Strike Selection</h3>
					<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Min Strike Gap</label>
							<input type="number" bind:value={form.min_strike_gap} step="50" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Strike Round To</label>
							<input type="number" bind:value={form.strike_round_to} step="50" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Expiry Offset Days</label>
							<input type="number" bind:value={form.expiry_offset_days} min="0" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
							<p class="text-xs text-gray-500 mt-1">0 = nearest, 1 = next week</p>
						</div>
					</div>
				</div>
				
				<!-- Other Settings -->
				<div class="border-t pt-4">
					<h3 class="text-lg font-semibold mb-3">Other Settings</h3>
					<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Square Off Time</label>
							<input 
								type="time" 
								bind:value={form.square_off_time} 
								class="w-full px-3 py-2 border border-gray-300 rounded-lg" 
								required
							/>
							<p class="text-xs text-gray-500 mt-1">Time to square off positions (24-hour format)</p>
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Tick Size (Backtest)</label>
							<input type="number" bind:value={form.tick_size} step="0.01" min="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
						</div>
					</div>
					<div class="mt-4 space-y-2">
						<label class="flex items-center space-x-2">
							<input type="checkbox" bind:checked={form.square_off_enabled} class="rounded" />
							<span class="text-sm">Enable Day End Square Off</span>
						</label>
						<label class="flex items-center space-x-2">
							<input type="checkbox" bind:checked={form.exclude_expiry_day_contracts} class="rounded" />
							<span class="text-sm">Exclude Expiry Day Contracts</span>
						</label>
						<label class="flex items-center space-x-2">
							<input type="checkbox" bind:checked={form.reverse_signals} class="rounded" />
							<span class="text-sm">Reverse Signals (Buy PE on Bullish, CE on Bearish)</span>
						</label>
					</div>
				</div>
				
				<!-- Form Actions -->
				<div class="flex justify-end space-x-4 pt-4">
					<button
						type="button"
						on:click={cancelForm}
						class="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
						disabled={loading}
					>
						Cancel
					</button>
					<button
						type="submit"
						class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
						disabled={loading}
					>
						{loading ? 'Saving...' : 'Save Configuration'}
					</button>
				</div>
			</form>
		</div>
	{/if}
	
	<!-- Configurations List -->
	<div class="bg-white rounded-lg shadow-lg p-6">
		<div class="flex justify-between items-center mb-4">
			<h2 class="text-2xl font-bold">All Configurations</h2>
			<button
				on:click={newConfig}
				class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
				disabled={loading}
			>
				New Configuration
			</button>
		</div>
		
		{#if loading && configs.length === 0}
			<div class="text-center py-8 text-gray-500">Loading...</div>
		{:else if configs.length === 0}
			<div class="text-center py-8 text-gray-500">
				No configurations found. Create your first configuration to get started.
			</div>
		{:else}
			<div class="grid grid-cols-3 gap-4">
				{#each configs as config}
					<div class="border rounded-lg p-4 {config.is_active ? 'border-green-500 bg-green-50' : 'border-gray-200'}">
						<div class="flex items-start justify-between mb-2">
							<div class="flex-1">
								<div class="flex items-center justify-between">
									<h3 class="font-semibold text-lg flex items-center">
										{config.name}
										{#if config.is_active}
											<span class="w-2 h-2 bg-green-500 rounded-full ml-2"></span>
										{/if}
									</h3>
									<div class="flex space-x-2">
										{#if !config.is_active}
											<button
												on:click={() => activateConfig(config)}
												class="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition"
												disabled={loading}
											>
												Activate
											</button>
										{/if}
										<button
											on:click={() => { selectConfig(config); editConfig(config); }}
											class="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition"
											disabled={loading}
										>
											Edit
										</button>
										<button
											on:click={() => deleteConfig(config)}
											class="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 transition"
											disabled={loading}
										>
											Delete
										</button>
									</div>
								</div>
								{#if config.description}
									<p class="text-sm text-gray-600 mt-1">{config.description}</p>
								{/if}
							</div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<style>
	/* Custom styles if needed */
</style>
