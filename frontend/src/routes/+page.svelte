<script>
	import { onMount, onDestroy } from 'svelte';
	import { broker } from '$lib/stores/broker';
	import { brokerAPI } from '$lib/utils/api';
	// Temporarily disabled until models are updated
	// import { portfolioAPI, positionsAPI, ordersAPI } from '$lib/utils/api';
	import { marketHoursAPI } from '$lib/utils/api';
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
	
	// Holiday card state
	let holidayData = null;
	let holidayLoading = false;
	let holidayError = null;
	let mounted = false;
	
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
		mounted = true;
		console.log('🎯 Component mounted, starting initialization...');
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
			
			// Load instrument status (independent, don't block other loads)
			loadInstrumentStatus().catch(err => {
				console.error('Error loading instrument status:', err);
			});
			
			// Load holiday data (independent, don't block other loads)
			loadHolidayData().then(() => {
				console.log('✅ Holiday data loaded successfully');
			}).catch(err => {
				console.error('❌ Error loading holiday data:', err);
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

	// Holiday card functions
	async function loadHolidayData() {
		try {
			holidayLoading = true;
			console.log('🏖️ Starting to load holiday data...');
			
			// Get today's market status using direct axios call
			const statusResponse = await axios.get('http://localhost:8000/api/market-time/status');
			console.log('✅ Today status:', statusResponse.data);
			
			// Get tomorrow's date and check if it's a trading day
			const tomorrow = new Date();
			tomorrow.setDate(tomorrow.getDate() + 1);
			const tomorrowStr = tomorrow.toISOString().split('T')[0];
			console.log('📅 Checking tomorrow:', tomorrowStr);
			
			const tomorrowResponse = await axios.get(`http://localhost:8000/api/market-time/is-trading-day?date=${tomorrowStr}`);
			console.log('✅ Tomorrow status:', tomorrowResponse.data);
			
			// Get next trading day
			const nextTradingResponse = await axios.get('http://localhost:8000/api/market-time/next-trading-day');
			console.log('✅ Next trading day:', nextTradingResponse.data);
			
			// Assign the data
			holidayData = {
				today: statusResponse.data,
				tomorrow: tomorrowResponse.data,
				nextTrading: nextTradingResponse.data
			};
			console.log('✅ Holiday data assigned:', holidayData);
			holidayError = null;
		} catch (err) {
			console.error('❌ Error loading holiday data:', err);
			holidayError = 'Failed to load: ' + (err.message || 'Unknown error');
			holidayData = null;
		} finally {
			holidayLoading = false;
			console.log('🏖️ Holiday data load complete');
		}
	}

</script>

	<!-- Content -->
	<div class="px-8 py-6">
		<!-- First Row: Configuration Cards -->
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
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
					
					<!-- Holiday Card -->
					<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
						<h2 class="text-lg font-bold text-gray-900 mb-4">🏖️ Holiday</h2>
						
						{#if holidayError}
							<div class="text-center py-4">
								<p class="text-sm text-red-600">{holidayError}</p>
							</div>
						{:else if holidayData}
							<div class="space-y-3">
								<!-- Today's market status -->
								<div class="flex items-center justify-between">
									<span class="text-sm font-medium text-gray-600">Market Status Today:</span>
									{#if holidayData.today.is_trading_day}
										<span class="text-sm font-bold text-green-600">
											Market open {holidayData.today.market_open_time} — {holidayData.today.market_close_time}
										</span>
									{:else}
										<span class="text-sm font-bold text-red-600">Market closed today</span>
									{/if}
								</div>
								
								<!-- Next session -->
								<div class="flex items-center justify-between">
									<span class="text-sm font-medium text-gray-600">Next Session:</span>
									<span class="text-sm font-bold text-gray-900">
										{new Date(holidayData.nextTrading.next_trading_day).toLocaleDateString('en-IN', { 
											day: '2-digit',
											month: '2-digit',
											year: 'numeric',
											weekday: 'short'
										})}
									</span>
								</div>
								
								<!-- Tomorrow's status (only if closed) -->
								{#if !holidayData.tomorrow.is_trading_day}
									<div class="flex items-center justify-between">
										<span class="text-sm font-medium text-gray-600">Tomorrow:</span>
										<span class="text-sm font-bold text-orange-600">
											{#if holidayData.tomorrow.is_weekend}
												Weekend close
											{:else}
												Holiday
											{/if}
										</span>
									</div>
								{/if}
							</div>
						{:else}
							<div class="text-center py-8">
								<p class="text-gray-500">Loading market data...</p>
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
