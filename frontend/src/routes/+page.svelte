<script>
	import { onMount, onDestroy } from 'svelte';
	import { broker } from '$lib/stores/broker';
	import { brokerAPI } from '$lib/utils/api';
	// Temporarily disabled until models are updated
	// import { portfolioAPI, positionsAPI, ordersAPI } from '$lib/utils/api';
	import { formatCurrency, getTrendColor } from '$lib/utils/helpers';
	import axios from 'axios';
	
	// State for sections visibility
	// Removed activeTab - only market-hours content now
	
	// Overview data
	let fundSummary = null;
	let positionsSummary = null;
	let openOrders = [];
	let loading = true;
	let statusCheckInterval = null;
	
	// Instrument download state
	let instrumentStatus = null;
	let instrumentLoading = false;
	let instrumentError = null;
	let instrumentSuccess = null;
	
	// Broker configuration
	let brokerLoading = false;
	let brokerError = null;
	let brokerSuccess = null;
	let brokerStatus = {
		connected: false,
		broker_type: 'kite',
		api_key: '',
		access_token: '',
		token_expired: false
	};
	
	let brokerConfig = {
		broker_type: 'kite',
		api_key: '',
		api_secret: '',
		redirect_url: '',
		postback_url: '',
		access_token: ''
	};
	
	let showApiSecret = false;
	let showAccessToken = false;
	let authWindow = null;
	let authCheckInterval = null;
	
	// Market Hours state
	let marketHours = {
		start_time: '09:15',
		end_time: '15:30',
		trading_days: [0, 1, 2, 3, 4],
		webhook_url: '',
		polling_interval_seconds: 300
	};
	let marketHoursLoading = false;
	let marketHoursSuccess = null;
	let marketHoursError = null;
	
	// Holidays state
	let holidays = [];
	let holidaysLoading = false;
	let holidaysError = null;
	let holidaysSuccess = null;
	let selectedYear = new Date().getFullYear();
	let showAddHolidayForm = false;
	let newHoliday = {
		date: '',
		name: '',
		description: ''
	};
	
	const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
	
	// Reactive statement to sync broker status
	// Reactive statement to sync broker status
	$: if ($broker) {
		brokerStatus.connected = $broker.connected;
		brokerStatus.broker_type = $broker.brokerType;
		brokerStatus.token_expired = $broker.tokenExpired || false;
	}
	
	// Reload holidays when year changes
	// Removed activeTab check - always load holidays now
	
	onMount(async () => {
		await initializeDashboard();
		
		// Check broker status every 30 seconds
		statusCheckInterval = setInterval(async () => {
			await broker.loadStatus('kite');
		}, 30000);
	});
	
	onDestroy(() => {
		if (authCheckInterval) clearInterval(authCheckInterval);
		if (statusCheckInterval) clearInterval(statusCheckInterval);
	});
	
	async function initializeDashboard() {
		try {
			// Load broker status
			await broker.loadStatus('kite');
			await loadBrokerStatus();
			await loadEnvConfig();
			await loadMarketHours();
			await loadHolidays();
			
			// Load instrument status (independent, don't block other loads)
			loadInstrumentStatus().catch(err => {
				console.error('Error loading instrument status:', err);
			});
			
			// Load overview data - temporarily disabled until models are updated
			// const fundResponse = await portfolioAPI.getFundSummary();
			// fundSummary = fundResponse.data;
			
			// const posResponse = await positionsAPI.getSummary();
			// positionsSummary = posResponse.data;
			
			// const ordersResponse = await ordersAPI.getOpen();
			// openOrders = ordersResponse.data;
		} catch (error) {
			console.error('Error loading dashboard:', error);
		} finally {
			loading = false;
		}
	}
	
	async function refreshOverview() {
		loading = true;
		try {
			// Temporarily disabled until models are updated
			// const fundResponse = await portfolioAPI.getFundSummary();
			// fundSummary = fundResponse.data;
			
			// const posResponse = await positionsAPI.getSummary();
			// positionsSummary = posResponse.data;
			
			// const ordersResponse = await ordersAPI.getOpen();
			// openOrders = ordersResponse.data;
		} catch (error) {
			console.error('Error refreshing data:', error);
		} finally {
			loading = false;
		}
	}
	
	// Broker functions
	async function loadEnvConfig() {
		brokerLoading = true;
		try {
			const response = await brokerAPI.getEnvConfig('kite');
			if (response.data) {
				brokerConfig = {
					...brokerConfig,
					api_key: response.data.api_key || '',
					api_secret: response.data.api_secret || '',
					redirect_url: response.data.redirect_url || '',
					postback_url: response.data.postback_url || ''
				};
			}
			
			await brokerAPI.initConfig('kite');
		} catch (err) {
			console.error('Error loading env config:', err);
		} finally {
			brokerLoading = false;
		}
	}
	
	async function loadBrokerStatus() {
		brokerLoading = true;
		try {
			await broker.loadStatus('kite');
			
			// Get the latest broker state
			const unsubscribe = broker.subscribe(state => {
				brokerStatus = {
					connected: state.connected,
					broker_type: state.brokerType,
					api_key: '',
					access_token: '',
					token_expired: false
				};
			});
			unsubscribe(); // Unsubscribe immediately after getting the value
			
			const configResponse = await brokerAPI.getConfig('kite');
			if (configResponse.data) {
				brokerConfig = {
					...brokerConfig,
					...configResponse.data
				};
			}
		} catch (err) {
			console.error('Error loading broker status:', err);
		} finally {
			brokerLoading = false;
		}
	}
	
	async function saveBrokerConfig() {
		brokerLoading = true;
		brokerError = null;
		brokerSuccess = null;
		
		try {
			await brokerAPI.createConfig(brokerConfig);
			await brokerAPI.updateEnvConfig('kite', {
				api_key: brokerConfig.api_key,
				api_secret: brokerConfig.api_secret,
				redirect_url: brokerConfig.redirect_url,
				postback_url: brokerConfig.postback_url
			});
			
			brokerSuccess = 'Broker configuration saved successfully!';
			await loadBrokerStatus();
			setTimeout(() => brokerSuccess = null, 3000);
		} catch (err) {
			console.error('Error saving broker config:', err);
			brokerError = err.response?.data?.detail || 'Failed to save broker configuration';
		} finally {
			brokerLoading = false;
		}
	}
	
	async function connectBroker() {
		brokerLoading = true;
		brokerError = null;
		
		try {
			await brokerAPI.createConfig(brokerConfig);
			const response = await brokerAPI.getAuthUrl('kite');
			const authUrl = response.data.auth_url;
			
			authWindow = window.open(authUrl, 'KiteAuth', 'width=800,height=600,scrollbars=yes');
			
			if (authWindow) {
				brokerSuccess = 'Please complete the authentication in the popup window.';
				
				authCheckInterval = setInterval(() => {
					if (authWindow && authWindow.closed) {
						clearInterval(authCheckInterval);
						authCheckInterval = null;
						loadBrokerStatus();
						loadEnvConfig();
					}
				}, 1000);
			} else {
				brokerError = 'Failed to open popup. Please allow popups for this site.';
			}
		} catch (err) {
			console.error('Error getting auth URL:', err);
			brokerError = err.response?.data?.detail || 'Failed to get authentication URL';
		} finally {
			brokerLoading = false;
		}
	}
	
	async function disconnectBroker() {
		if (!confirm('Are you sure you want to disconnect the broker?')) return;
		
		brokerLoading = true;
		brokerError = null;
		brokerSuccess = null;
		
		try {
			await brokerAPI.disconnect('kite');
			brokerSuccess = 'Broker disconnected successfully!';
			brokerConfig.access_token = '';
			await loadBrokerStatus();
			setTimeout(() => brokerSuccess = null, 3000);
		} catch (err) {
			console.error('Error disconnecting broker:', err);
			brokerError = 'Failed to disconnect broker';
		} finally {
			brokerLoading = false;
		}
	}
	
	// Market Hours functions
	async function loadMarketHours() {
		marketHoursLoading = true;
		marketHoursError = null;
		
		try {
			const response = await axios.get('http://localhost:8000/api/market-hours');
			marketHours = response.data;
		} catch (err) {
			console.error('Error loading market hours:', err);
			marketHoursError = 'Failed to load market hours configuration';
		} finally {
			marketHoursLoading = false;
		}
	}
	
	async function saveMarketHours() {
		marketHoursLoading = true;
		marketHoursError = null;
		marketHoursSuccess = null;
		
		try {
			const response = await axios.put('http://localhost:8000/api/market-hours', marketHours);
			marketHoursSuccess = 'Market hours configuration saved successfully!';
			setTimeout(() => marketHoursSuccess = null, 3000);
		} catch (err) {
			console.error('Error saving market hours:', err);
			marketHoursError = err.response?.data?.detail || 'Failed to save market hours configuration';
		} finally {
			marketHoursLoading = false;
		}
	}
	
	function toggleTradingDay(dayIndex) {
		const index = marketHours.trading_days.indexOf(dayIndex);
		if (index > -1) {
			marketHours.trading_days = marketHours.trading_days.filter(d => d !== dayIndex);
		} else {
			marketHours.trading_days = [...marketHours.trading_days, dayIndex].sort();
		}
	}
	
	// Holiday management functions
	async function loadHolidays() {
		holidaysLoading = true;
		holidaysError = null;
		
		try {
			const url = selectedYear 
				? `http://localhost:8000/api/market-hours/holidays?year=${selectedYear}`
				: 'http://localhost:8000/api/market-hours/holidays';
			const response = await axios.get(url);
			holidays = response.data;
		} catch (err) {
			console.error('Error loading holidays:', err);
			holidaysError = 'Failed to load holidays';
		} finally {
			holidaysLoading = false;
		}
	}
	
	async function addHoliday() {
		if (!newHoliday.date || !newHoliday.name) {
			holidaysError = 'Date and name are required';
			return;
		}
		
		holidaysLoading = true;
		holidaysError = null;
		holidaysSuccess = null;
		
		try {
			await axios.post('http://localhost:8000/api/market-hours/holidays', newHoliday);
			holidaysSuccess = 'Holiday added successfully!';
			setTimeout(() => holidaysSuccess = null, 3000);
			
			// Reset form
			newHoliday = { date: '', name: '', description: '' };
			showAddHolidayForm = false;
			
			// Reload holidays
			await loadHolidays();
		} catch (err) {
			console.error('Error adding holiday:', err);
			holidaysError = err.response?.data?.detail || 'Failed to add holiday';
		} finally {
			holidaysLoading = false;
		}
	}
	
	async function deleteHoliday(date) {
		if (!confirm(`Are you sure you want to delete the holiday on ${date}?`)) {
			return;
		}
		
		holidaysLoading = true;
		holidaysError = null;
		holidaysSuccess = null;
		
		try {
			await axios.delete(`http://localhost:8000/api/market-hours/holidays/${date}`);
			holidaysSuccess = 'Holiday deleted successfully!';
			setTimeout(() => holidaysSuccess = null, 3000);
			
			// Reload holidays
			await loadHolidays();
		} catch (err) {
			console.error('Error deleting holiday:', err);
			holidaysError = err.response?.data?.detail || 'Failed to delete holiday';
		} finally {
			holidaysLoading = false;
		}
	}
	
	function formatDate(dateStr) {
		const date = new Date(dateStr + 'T00:00:00');
		return date.toLocaleDateString('en-IN', { 
			weekday: 'short',
			year: 'numeric', 
			month: 'short', 
			day: 'numeric' 
		});
	}
	
	// Instrument download functions
	async function loadInstrumentStatus() {
		instrumentLoading = true;
		instrumentError = null;
		
		try {
			const response = await axios.get('http://localhost:8000/api/broker/instruments/status/kite');
			instrumentStatus = response.data;
		} catch (err) {
			console.error('Error loading instrument status:', err);
			instrumentError = 'Failed to load instrument status';
		} finally {
			instrumentLoading = false;
		}
	}
	
	async function downloadInstruments() {
		instrumentLoading = true;
		instrumentError = null;
		instrumentSuccess = null;
		
		try {
			const response = await axios.post('http://localhost:8000/api/broker/instruments/download/kite');
			instrumentSuccess = `Downloaded ${response.data.count} instruments successfully!`;
			setTimeout(() => instrumentSuccess = null, 3000);
			
			// Reload status
			await loadInstrumentStatus();
		} catch (err) {
			console.error('Error downloading instruments:', err);
			instrumentError = err.response?.data?.detail || 'Failed to download instruments';
		} finally {
			instrumentLoading = false;
		}
	}
	
	function formatDateTime(dateStr) {
		if (!dateStr) return 'Never';
		const date = new Date(dateStr);
		return date.toLocaleString('en-IN', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}


</script>

	<!-- Content -->
	<div class="px-8 py-6">
		<!-- First Row: Configuration Cards -->
		<div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
					<!-- Kite Connect Configuration -->
					<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
						<h2 class="text-xl font-bold mb-4 text-gray-900 flex items-center gap-2">
							Kite Connect Configuration
							<div class="w-4 h-4 rounded-full {brokerStatus.connected ? 'bg-green-500' : 'bg-red-500'}"></div>
						</h2>
						
						{#if brokerSuccess}
							<div class="bg-green-50 border border-green-200 text-green-800 p-4 rounded-lg mb-4">
								{brokerSuccess}
							</div>
						{/if}
						
						{#if brokerError}
							<div class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg mb-4">
								{brokerError}
							</div>
						{/if}
						
						<form on:submit|preventDefault={saveBrokerConfig} class="space-y-4">
							<div>
								<label for="api-key" class="block text-sm font-medium text-gray-700 mb-1">API Key *</label>
								<input
									id="api-key"
									type="text"
									bind:value={brokerConfig.api_key}
									required
									placeholder="Enter your Kite API Key"
									class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
								/>
								<p class="text-xs text-gray-600 mt-1">
									Get your API key from <a href="https://kite.trade/" target="_blank" class="text-blue-600 hover:underline">kite.trade</a>
								</p>
							</div>
							
						<div>
							<label for="api-secret" class="block text-sm font-medium text-gray-700 mb-1">API Secret *</label>
							<div class="relative">
								{#if showApiSecret}
									<input
										id="api-secret"
										type="text"
										bind:value={brokerConfig.api_secret}
										required
										placeholder="Enter your Kite API Secret"
										class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-10"
									/>
								{:else}
									<input
										id="api-secret"
										type="password"
										bind:value={brokerConfig.api_secret}
										required
										placeholder="Enter your Kite API Secret"
										class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-10"
									/>
								{/if}
								<button
									type="button"
									on:click={() => showApiSecret = !showApiSecret}
									class="absolute right-3 top-3 text-gray-600 hover:text-gray-900"
								>
									{showApiSecret ? '🙈' : '👁️'}
								</button>
							</div>
						</div>						<div>
							<label for="redirect-url" class="block text-sm font-medium text-gray-700 mb-1">Redirect URL</label>
							<input
								id="redirect-url"
								type="text"
								bind:value={brokerConfig.redirect_url}
								placeholder="https://your-domain.com/api/broker/callback"
								class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
							/>
						</div>
						
						<div>
							<label for="postback-url" class="block text-sm font-medium text-gray-700 mb-1">Postback URL (Optional)</label>
							<input
								id="postback-url"
								type="text"
								bind:value={brokerConfig.postback_url}
								placeholder="https://your-domain.com/api/broker/postback"
								class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
							/>
						</div>
						
						<div class="flex gap-3 pt-4">
							<button
								type="submit"
								disabled={brokerLoading}
								class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 w-32"
							>
								{brokerLoading ? 'Saving...' : 'Save'}
							</button>
							
							<button
								type="button"
								on:click={brokerStatus.connected ? disconnectBroker : connectBroker}
								disabled={brokerLoading || (!brokerStatus.connected && (!brokerConfig.api_key || !brokerConfig.api_secret))}
								class="px-6 py-2 {brokerStatus.connected ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'} text-white rounded-lg disabled:opacity-50 w-32"
							>
								{brokerStatus.connected ? 'Disconnect' : 'Connect Broker'}
							</button>
						</div>
					</form>
				</div>
					
					<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
						<h2 class="text-xl font-bold mb-4 text-gray-900">Market Hours Configuration</h2>
						
						{#if marketHoursSuccess}
							<div class="bg-green-50 border border-green-200 text-green-800 p-4 rounded-lg mb-4">
								{marketHoursSuccess}
							</div>
						{/if}
						
						{#if marketHoursError}
							<div class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg mb-4">
								{marketHoursError}
							</div>
						{/if}
						
						<form on:submit|preventDefault={saveMarketHours} class="space-y-6">
						<!-- Market Hours Time Range -->
						<div class="grid grid-cols-2 gap-4">
							<div>
								<label for="market-open-time" class="block text-sm font-medium text-gray-700 mb-1">Market Open Time</label>
								<input
									id="market-open-time"
									type="time"
									bind:value={marketHours.start_time}
									class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
								/>
							</div>
							<div>
								<label for="market-close-time" class="block text-sm font-medium text-gray-700 mb-1">Market Close Time</label>
								<input
									id="market-close-time"
									type="time"
									bind:value={marketHours.end_time}
									class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
								/>
							</div>
						</div>
						
						<!-- Trading Days -->
						<div>
							<div class="block text-sm font-medium text-gray-700 mb-2">Trading Days</div>
							<div class="flex flex-wrap gap-2">
								{#each dayNames as day, index}
									<button
										type="button"
										on:click={() => toggleTradingDay(index)}
										class="px-4 py-2 rounded-lg text-sm font-medium transition-colors {
											marketHours.trading_days.includes(index)
												? 'bg-blue-600 text-white hover:bg-blue-700'
												: 'bg-gray-100 text-gray-700 hover:bg-gray-200'
										}"
									>
										{day}
									</button>
								{/each}
							</div>
						</div>
						
						<!-- Webhook Configuration -->
							<div class="border-t pt-6">
								<div class="mb-3">
									<div class="font-medium text-gray-900">Real-time Updates (Webhook)</div>
									<p class="text-sm text-gray-600">Webhook is automatically enabled during market hours for instant order updates</p>
								</div>
								<label for="webhook-url" class="block text-sm font-medium text-gray-700 mb-1">Webhook URL (Optional)</label>
								<input
									id="webhook-url"
									type="text"
									bind:value={marketHours.webhook_url}
									placeholder="https://your-domain.com/api/webhook/kite-postback"
									class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
								/>
							</div>
							
							<!-- Polling Configuration -->
							<div class="border-t pt-6">
								<div class="mb-3">
									<div class="font-medium text-gray-900">API Polling (Outside Market Hours)</div>
									<p class="text-sm text-gray-600">API polling is automatically enabled outside market hours to fetch order status periodically</p>
								</div>
							<div>
								<label for="polling-interval" class="block text-sm font-medium text-gray-700 mb-1">Polling Interval (seconds)</label>
								<input
									id="polling-interval"
									type="number"
									bind:value={marketHours.polling_interval_seconds}
									min="60"
									max="3600"
									step="60"
									class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
								/>
								<p class="text-xs text-gray-600 mt-1">Minimum 60 seconds, recommended 300</p>
							</div>
							</div>
							
							<div class="flex gap-3 pt-4">
								<button
									type="submit"
									disabled={marketHoursLoading}
									class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
								>
									{marketHoursLoading ? 'Saving...' : 'Save Market Hours'}
								</button>
							</div>
						</form>
					</div>
					
					<!-- Holidays Management -->
					<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
						<div class="flex justify-between items-center mb-4">
							<h2 class="text-xl font-bold text-gray-900">Holidays Management</h2>
							<div class="flex gap-3 items-center">
								<select 
									bind:value={selectedYear}
									class="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
								>
									<option value={2024}>2024</option>
									<option value={2025}>2025</option>
									<option value={2026}>2026</option>
								</select>
								<button
									on:click={() => showAddHolidayForm = !showAddHolidayForm}
									class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
								>
									<span>{showAddHolidayForm ? '✕' : '+'}</span>
									{showAddHolidayForm ? 'Cancel' : 'Add Holiday'}
								</button>
							</div>
						</div>
						
						{#if holidaysSuccess}
							<div class="bg-green-50 border border-green-200 text-green-800 p-4 rounded-lg mb-4">
								{holidaysSuccess}
							</div>
						{/if}
						
						{#if holidaysError}
							<div class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg mb-4">
								{holidaysError}
							</div>
						{/if}
						
						<!-- Add Holiday Form -->
						{#if showAddHolidayForm}
							<div class="bg-gray-50 rounded-lg p-4 mb-4 border border-gray-200">
								<h3 class="text-lg font-semibold mb-3 text-gray-900">Add New Holiday</h3>
								<form on:submit|preventDefault={addHoliday} class="space-y-4">
									<div class="grid grid-cols-2 gap-4">
										<div>
											<label for="holiday-date" class="block text-sm font-medium text-gray-700 mb-1">
												Date <span class="text-red-500">*</span>
											</label>
											<input
												id="holiday-date"
												type="date"
												bind:value={newHoliday.date}
												required
												class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
											/>
										</div>
										<div>
											<label for="holiday-name" class="block text-sm font-medium text-gray-700 mb-1">
												Holiday Name <span class="text-red-500">*</span>
											</label>
											<input
												id="holiday-name"
												type="text"
												bind:value={newHoliday.name}
												placeholder="e.g., Independence Day"
												required
												class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
											/>
										</div>
									</div>
									<div>
										<label for="holiday-description" class="block text-sm font-medium text-gray-700 mb-1">
											Description (Optional)
										</label>
										<input
											id="holiday-description"
											type="text"
											bind:value={newHoliday.description}
											placeholder="Additional notes about this holiday"
											class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
										/>
									</div>
									<div class="flex gap-3">
										<button
											type="submit"
											disabled={holidaysLoading}
											class="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
										>
											{holidaysLoading ? 'Adding...' : 'Add Holiday'}
										</button>
										<button
											type="button"
											on:click={() => {
												showAddHolidayForm = false;
												newHoliday = { date: '', name: '', description: '' };
											}}
											class="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
										>
											Cancel
										</button>
									</div>
								</form>
							</div>
						{/if}
						
						<!-- Holidays List -->
						{#if holidaysLoading}
							<div class="text-center py-8">
								<div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
								<p class="text-gray-600 mt-2">Loading holidays...</p>
							</div>
						{:else if holidays.length === 0}
							<div class="text-center py-8 text-gray-500">
								<svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
								</svg>
								<p class="mt-2">No holidays found for {selectedYear}</p>
							</div>
						{:else}
							<div class="space-y-2">
								<div class="text-sm text-gray-600 mb-2">
									Total: {holidays.length} holiday{holidays.length !== 1 ? 's' : ''}
								</div>
								<div class="max-h-96 overflow-y-auto">
									{#each holidays as holiday}
										<div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors border border-gray-200 mb-2">
											<div class="flex-1">
												<div class="flex items-center gap-3">
													<div class="text-sm font-medium text-gray-500 min-w-[120px]">
														{formatDate(holiday.date)}
													</div>
													<div class="flex-1">
														<div class="font-semibold text-gray-900">{holiday.name}</div>
														{#if holiday.description}
															<div class="text-sm text-gray-600">{holiday.description}</div>
														{/if}
													</div>
												</div>
											</div>
											<button
												on:click={() => deleteHoliday(holiday.date)}
												disabled={holidaysLoading}
												class="ml-4 px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm"
												title="Delete holiday"
											>
												🗑️ Delete
											</button>
										</div>
									{/each}
								</div>
							</div>
						{/if}
					</div>
				
				<!-- Second Row: Instrument Data and Fund Cards -->
				<div class="grid grid-cols-1 gap-6">
					<!-- Instrument Download Status -->
					<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
						<div class="flex items-center justify-between mb-4">
							<h2 class="text-lg font-bold text-gray-900 flex items-center gap-2">
								📥 Instrument Data
								{#if instrumentStatus}
									<div class="w-3 h-3 rounded-full {instrumentStatus.downloaded_today ? 'bg-green-500' : 'bg-red-500'}"></div>
								{/if}
							</h2>
							<button
								on:click={downloadInstruments}
								disabled={instrumentLoading}
								class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm flex items-center gap-1"
							>
								<span>📥</span>
								{instrumentLoading ? 'Downloading...' : 'Download'}
							</button>
						</div>
						
						{#if instrumentSuccess}
							<div class="bg-green-50 border border-green-200 text-green-800 p-4 rounded-lg mb-4 text-sm">
								{instrumentSuccess}
							</div>
						{/if}
						
						{#if instrumentError}
							<div class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg mb-4 text-sm">
								{instrumentError}
							</div>
						{/if}
						
						{#if instrumentLoading}
							<div class="text-center py-8">
								<div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
								<p class="text-gray-600 mt-2">Loading...</p>
							</div>
						{:else if instrumentStatus}
							<div class="flex gap-6">
								<div>
									<p class="text-sm font-medium text-gray-600">Total Instruments</p>
									<p class="text-xl font-bold text-gray-900">{instrumentStatus.count?.toLocaleString() || 0}</p>
								</div>
								<div>
									<p class="text-sm font-medium text-gray-600">Last Downloaded</p>
									<p class="text-sm text-gray-700">{formatDateTime(instrumentStatus.last_download)}</p>
								</div>
							</div>
						{/if}
					</div>
					
					<!-- Fund Card -->
					{#if fundSummary}
						<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
							<h2 class="text-lg font-bold text-gray-900 mb-4">💰 Fund Summary</h2>
							<div class="space-y-3">
								<div>
									<p class="text-sm font-medium text-gray-600">Available Balance</p>
									<p class="text-2xl font-bold text-gray-900">{formatCurrency(fundSummary.available_balance)}</p>
								</div>
								{#if fundSummary.used_margin}
									<div>
										<p class="text-sm font-medium text-gray-600">Used Margin</p>
										<p class="text-lg font-semibold text-gray-700">{formatCurrency(fundSummary.used_margin)}</p>
									</div>
								{/if}
								{#if fundSummary.net}
									<div>
										<p class="text-sm font-medium text-gray-600">Net Value</p>
										<p class="text-lg font-semibold text-gray-700">{formatCurrency(fundSummary.net)}</p>
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>
		</div>
	</div>
