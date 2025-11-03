<script>
	import { onMount, onDestroy } from 'svelte';
	import { paperTradingAPI, configAPI } from '$lib/utils/api';

	// Engine Status
	let engineStatus = {
		running: false,
		status: 'stopped',
		mode: 'none',
		is_historical_mode: false,
		config_id: null,
		initial_capital: 0,
		current_capital: 0,
		nifty_ltp: 0,
		major_trend: '',
		major_ma7: null,
		major_ma20: null,
		major_trend_changed_at: null,
		minor_trend: '',
		minor_ma7: null,
		minor_ma20: null,
		minor_trend_changed_at: null,
		major_timeframe: '15min',
		minor_timeframe: '1min',
		active_positions: 0,
		last_update: null,
		current_simulation_time: null,
		suspend_ce: false,
		suspend_pe: false
	};

	// Market Status
	let marketStatus = {
		is_open: false,
		current_time: '',
		is_trading_day: false,
		market_open_time: '09:15',
		market_close_time: '15:30',
		next_trading_day: null
	};

	// Performance Metrics
	let performance = {
		total_trades: 0,
		call_trades: 0,
		put_trades: 0,
		realized_pnl: 0,
		unrealized_pnl: 0,
		total_pnl: 0,
		win_rate: 0,
		avg_profit: 0,
		avg_loss: 0
	};

	// UI State
	let error = null;
	let loading = false;
	let activeTrades = [];
	let closedTrades = [];
	let alerts = [];
	let configs = [];
	let selectedConfig = null;
	let enableHistoricalMode = false;  // Checkbox for historical simulation
	let replaySpeed = 1.0;  // Speed multiplier for historical replay (1.0 = real-time)
	let selectedDate = null;  // Selected date for historical data
	let instruments = [];  // Available instruments for trading

	// Tab state
	let mainTab = 'dash';
	let activeTab = 'performance';
	let tradingInfoTab = 'instruments'; // For the trading info tabs in dashboard

	// Polling interval
	let statusInterval = null;

	onMount(async () => {
		await loadConfigs();
		await loadMarketStatus();
		await updateStatus();
		statusInterval = setInterval(updateStatus, 5000);
	});

	onDestroy(() => {
		if (statusInterval) {
			clearInterval(statusInterval);
		}
	});

	async function updateStatus() {
		try {
			const response = await paperTradingAPI.getStatus();
			engineStatus = { ...engineStatus, ...response.data };

			if (engineStatus.running && engineStatus.config_id) {
				await loadTrades();
				await loadAlerts();
				await loadInstruments();
			}
		} catch (err) {
			console.error('Error fetching status:', err);
		}
	}

	async function loadConfigs() {
		try {
			const response = await configAPI.getAll();
			configs = response.data.configs || [];
			if (configs.length > 0 && !selectedConfig) {
				selectedConfig = configs[0].id;
			}
		} catch (err) {
			console.error('Error loading configs:', err);
		}
	}

	async function loadMarketStatus() {
		try {
			const response = await fetch('http://localhost:8000/api/paper-trading/market-status');
			const result = await response.json();
			if (result.status === 'success') {
				marketStatus = result.data;
				// Auto-disable historical mode if market is open
				if (marketStatus.is_open) {
					enableHistoricalMode = false;
				}
			}
		} catch (err) {
			console.error('Error loading market status:', err);
		}
	}

	async function loadTrades() {
		if (!engineStatus.config_id) return;

		try {
			const response = await paperTradingAPI.getTrades(engineStatus.config_id);
			const trades = response.data.trades || [];

			activeTrades = trades.filter(t => t.status === 'open');
			closedTrades = trades.filter(t => t.status === 'closed').slice(0, 50);

			// Calculate performance metrics
			performance.total_trades = closedTrades.length;
			performance.call_trades = closedTrades.filter(t => t.option_type === 'CE').length;
			performance.put_trades = closedTrades.filter(t => t.option_type === 'PE').length;
			performance.realized_pnl = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
			performance.unrealized_pnl = activeTrades.reduce((sum, t) => sum + (t.unrealized_pnl || 0), 0);
			performance.total_pnl = performance.realized_pnl + performance.unrealized_pnl;

			const closedWithPnl = closedTrades.filter(t => t.pnl !== 0);
			const winners = closedWithPnl.filter(t => t.pnl > 0);
			performance.win_rate = closedWithPnl.length > 0
				? (winners.length / closedWithPnl.length * 100).toFixed(1)
				: 0;

		} catch (err) {
			console.error('Error loading trades:', err);
		}
	}

	async function loadAlerts() {
		if (!engineStatus.config_id) return;

		try {
			const response = await paperTradingAPI.getAlerts(engineStatus.config_id);
			alerts = (response.data.alerts || []).slice(0, 100);
		} catch (err) {
			console.error('Error loading alerts:', err);
		}
	}

	async function loadInstruments() {
		if (!engineStatus.config_id) return;

		try {
			const response = await fetch(`http://localhost:8000/api/paper-trading/instruments/${engineStatus.config_id}`);
			const result = await response.json();
			if (result.status === 'success') {
				instruments = result.instruments || [];
			}
		} catch (err) {
			console.error('Error loading instruments:', err);
		}
	}

	async function startEngine() {
		if (!selectedConfig) {
			error = 'Please select a configuration';
			return;
		}

		loading = true;
		error = null;

		try {
			// Send historical_mode parameter to API
			const response = await fetch('http://localhost:8000/api/paper-trading/start', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					config_id: selectedConfig,
					historical_mode: enableHistoricalMode,
					replay_speed: enableHistoricalMode ? replaySpeed : 1.0,
					selected_date: enableHistoricalMode && selectedDate ? selectedDate : null
				})
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to start engine');
			}

			await updateStatus();
		} catch (err) {
			error = err.message || 'Failed to start engine';
			console.error('Error starting engine:', err);
		} finally {
			loading = false;
		}
	}

	async function stopEngine() {
		loading = true;
		error = null;

		try {
			await paperTradingAPI.stop();
			await updateStatus();
		} catch (err) {
			error = err.response?.data?.detail || 'Failed to stop engine';
			console.error('Error stopping engine:', err);
		} finally {
			loading = false;
		}
	}

	async function pauseEngine() {
		loading = true;
		error = null;

		try {
			await paperTradingAPI.pause();
			await updateStatus();
		} catch (err) {
			error = err.response?.data?.detail || 'Failed to pause engine';
			console.error('Error pausing engine:', err);
		} finally {
			loading = false;
		}
	}

	async function resumeEngine() {
		loading = true;
		error = null;

		try {
			await paperTradingAPI.resume();
			await updateStatus();
		} catch (err) {
			error = err.response?.data?.detail || 'Failed to resume engine';
			console.error('Error resuming engine:', err);
		} finally {
			loading = false;
		}
	}

	async function toggleSuspendCE(suspend) {
		try {
			await paperTradingAPI.suspendCE(suspend);
			await updateStatus();
		} catch (err) {
			error = err.response?.data?.detail || 'Failed to toggle CE suspension';
			console.error('Error toggling CE:', err);
		}
	}

	async function toggleSuspendPE(suspend) {
		try {
			await paperTradingAPI.suspendPE(suspend);
			await updateStatus();
		} catch (err) {
			error = err.response?.data?.detail || 'Failed to toggle PE suspension';
			console.error('Error toggling PE:', err);
		}
	}

	async function closePosition(tradeId) {
		if (!confirm('Are you sure you want to close this position?')) return;

		try {
			await paperTradingAPI.closePosition(tradeId);
			await loadTrades();
		} catch (err) {
			error = err.response?.data?.detail || 'Failed to close position';
			console.error('Error closing position:', err);
		}
	}

	function formatCurrency(value) {
		return new Intl.NumberFormat('en-IN', {
			minimumFractionDigits: 0,
			maximumFractionDigits: 0
		}).format(value);
	}

	function formatDateTime(dateStr) {
		if (!dateStr) return '-';
		return new Date(dateStr).toLocaleString('en-IN');
	}

	function formatTime(dateStr) {
		if (!dateStr) return '-';
		return new Date(dateStr).toLocaleTimeString('en-IN');
	}

	function getStatusColor(status) {
		const colors = {
			'running': 'text-green-600 bg-green-100',
			'paused': 'text-yellow-600 bg-yellow-100',
			'stopped': 'text-gray-600 bg-gray-100'
		};
		return colors[status] || 'text-gray-600 bg-gray-100';
	}

	function getTrendColor(trend) {
		if (!trend) return 'text-gray-500';
		return trend.toLowerCase().includes('up') ? 'text-green-600' : 'text-red-600';
	}

	function getTrendDotColor(trend) {
		if (!trend) return 'bg-gray-400';
		return trend.toLowerCase().includes('up') ? 'bg-green-500' : 'bg-red-500';
	}

	function formatTrend(trend) {
		if (!trend) return '-';
		return trend.toLowerCase().includes('up') ? 'Up' : 'Down';
	}

	function getPnLColor(pnl) {
		if (pnl > 0) return 'text-green-600';
		if (pnl < 0) return 'text-red-600';
		return 'text-gray-600';
	}

</script>

<div class="space-y-6">
	<!-- Header -->
	<div class="flex justify-between items-center">
		<div>
			<h1 class="text-3xl font-bold text-gray-900">Mock</h1>
			<p class="text-gray-600 mt-1">Real-time mock trading with live market data</p>
		</div>
		<div class="flex items-center gap-3">
			<!-- Mode Badge -->
			{#if engineStatus.running}
				<div class="px-4 py-2 rounded-lg font-semibold {
					engineStatus.is_historical_mode 
						? 'bg-purple-100 text-purple-700' 
						: 'bg-blue-100 text-blue-700'
				}">
					{engineStatus.is_historical_mode ? '🕒 HISTORICAL' : '📡 LIVE'}
				</div>
			{/if}
			<!-- Status Badge -->
			<div class="px-4 py-2 rounded-lg {getStatusColor(engineStatus.status)} font-semibold">
				{engineStatus.status.toUpperCase()}
			</div>
		</div>
	</div>

	<!-- Main Tabs -->
	<div class="border-b border-gray-200">
		<div class="flex gap-1 p-2">
			<button
				on:click={() => mainTab = 'dash'}
				class="px-6 py-3 rounded-t-lg font-medium transition-colors {mainTab === 'dash' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
			>
				🏠 Dashboard
			</button>
			<button
				on:click={() => mainTab = 'trades'}
				class="px-6 py-3 rounded-t-lg font-medium transition-colors {mainTab === 'trades' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
			>
				📊 Trades
			</button>
		</div>
	</div>

	<!-- Error Display -->
	{#if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4">
			<div class="flex items-start gap-3">
				<span class="text-red-600 text-xl">⚠️</span>
				<div class="flex-1">
					<h3 class="text-red-800 font-semibold">Error</h3>
					<p class="text-red-700 text-sm mt-1">{error}</p>
				</div>
				<button on:click={() => error = null} class="text-red-600 hover:text-red-800">✕</button>
			</div>
		</div>
	{/if}

		<!-- Dashboard Tab -->
		{#if mainTab === 'dash'}
			<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
				<!-- Controls -->
				<div class="bg-white rounded-lg shadow-md p-6">
					<h2 class="text-xl font-bold mb-4">Controls</h2>
					<div class="mb-4">
						<label for="config-select" class="block text-sm font-medium text-gray-700 mb-2">Configuration</label>
						<select
							id="config-select"
							bind:value={selectedConfig}
							disabled={engineStatus.running}
							class="w-full px-4 py-2 border rounded-lg disabled:bg-gray-100"
						>
							{#each configs as config}
								<option value={config.id}>{config.name}</option>
							{/each}
					</select>
					<p class="text-xs text-gray-600 mt-2">
						Manage configurations on the <a href="/config" class="text-blue-600 hover:underline font-semibold">Config</a> page.
					</p>
				</div>					<!-- Historical Simulation Mode -->
					{#if !engineStatus.running}
						<div class="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
							<label class="flex items-start gap-3 cursor-pointer">
								<input
									type="checkbox"
									bind:checked={enableHistoricalMode}
									disabled={marketStatus.is_open}
									class="w-5 h-5 mt-0.5"
								/>
								<div class="flex-1">
									<span class="text-sm font-medium text-gray-900">Enable Historical Simulation</span>
									<p class="text-xs text-gray-600 mt-1">
										{#if marketStatus.is_open}
											Market is currently open - Historical mode unavailable
										{:else}
											Replay historical market data for practice (Market is closed)
										{/if}
									</p>
									{#if !marketStatus.is_trading_day && marketStatus.next_trading_day}
										<p class="text-xs text-purple-600 mt-1">
											Next trading day: {marketStatus.next_trading_day}
										</p>
									{/if}
								</div>
							</label>

							<!-- Speed Control for Historical Mode -->
							{#if enableHistoricalMode && !marketStatus.is_open}
								<div class="mt-4 pt-4 border-t border-gray-200">
									<label for="replay-speed" class="block text-sm font-medium text-gray-700 mb-2">
										Replay Speed: {replaySpeed}x
									</label>
									<div class="flex items-center gap-4">
										<input
											id="replay-speed"
											type="range"
											min="0.1"
											max="5.0"
											step="0.1"
											bind:value={replaySpeed}
											class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
										/>
										<div class="flex gap-2">
											<button
												on:click={() => replaySpeed = 0.5}
												class="px-3 py-1 text-xs bg-gray-200 hover:bg-gray-300 rounded"
											>
												0.5x
											</button>
											<button
												on:click={() => replaySpeed = 1.0}
												class="px-3 py-1 text-xs bg-blue-600 text-white hover:bg-blue-700 rounded"
											>
												1.0x
											</button>
											<button
												on:click={() => replaySpeed = 2.0}
												class="px-3 py-1 text-xs bg-gray-200 hover:bg-gray-300 rounded"
											>
												2.0x
											</button>
										</div>
									</div>
									<p class="text-xs text-gray-500 mt-1">
										Adjust replay speed: 0.5x = half speed, 1.0x = real-time, 2.0x = double speed
									</p>
								</div>

								<!-- Date Selection for Historical Mode -->
								<div class="mt-4 pt-4 border-t border-gray-200">
									<label for="historical-date" class="block text-sm font-medium text-gray-700 mb-2">
										Select Date for Historical Data
									</label>
									<input
										id="historical-date"
										type="date"
										bind:value={selectedDate}
										max={new Date().toISOString().split('T')[0]}
										class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
									/>
									<p class="text-xs text-gray-500 mt-1">
										Choose a trading day to replay. Leave empty for yesterday's data.
									</p>
								</div>
							{/if}
						</div>
					{:else if engineStatus.is_historical_mode}
						<div class="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
							<div class="flex items-center gap-2">
								<span class="text-lg">🕒</span>
								<div class="flex-1">
									<p class="text-sm font-medium text-purple-900">Historical Simulation Active</p>
									<p class="text-xs text-purple-700">Replaying historical market data at {replaySpeed}x speed</p>
								</div>
							</div>
						</div>
					{/if}

					<div class="space-y-2">
						{#if !engineStatus.running}
							<button
								on:click={startEngine}
								disabled={loading || !selectedConfig}
								class="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 font-semibold"
							>
								▶ Start Trading
							</button>
						{:else if engineStatus.status === 'paused'}
							<button
								on:click={resumeEngine}
								disabled={loading}
								class="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold"
							>
								▶ Resume
							</button>
						{:else}
							<button
								on:click={pauseEngine}
								disabled={loading}
								class="w-full px-4 py-3 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 font-semibold"
							>
								⏸ Pause
							</button>
						{/if}

						{#if engineStatus.running}
							<button
								on:click={stopEngine}
								disabled={loading}
								class="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold"
							>
								⏹ Stop & Close All
							</button>
						{/if}
					</div>

					{#if engineStatus.running}
						<div class="mt-6 pt-6 border-t">
							<h3 class="text-sm font-semibold mb-3">Suspension Controls</h3>
							<div class="space-y-2">
								<label class="flex items-center gap-2">
									<input
										type="checkbox"
										checked={engineStatus.suspend_ce || false}
										on:change={(e) => toggleSuspendCE(e.target.checked)}
										class="w-5 h-5"
									/>
									<span class="text-sm">Suspend CE Entries</span>
								</label>
								<label class="flex items-center gap-2">
									<input
										type="checkbox"
										checked={engineStatus.suspend_pe || false}
										on:change={(e) => toggleSuspendPE(e.target.checked)}
										class="w-5 h-5"
									/>
									<span class="text-sm">Suspend PE Entries</span>
								</label>
							</div>
						</div>
					{/if}
				</div>

				<!-- Market Data -->
				<div class="lg:col-span-2 bg-white rounded-lg shadow-md p-6">
					<div class="flex justify-between items-center mb-4">
						<h2 class="text-xl font-bold">
							Nifty 50
							{#if engineStatus.nifty_ltp}
								<span class="text-2xl font-bold text-blue-600 ml-2">
									{engineStatus.nifty_ltp}
								</span>
							{/if}
							{#if engineStatus.running && engineStatus.last_update}
								<span class="text-lg font-normal text-blue-600 ml-2">
									{formatTime(engineStatus.last_update)}
								</span>
							{/if}
						</h2>
						<div class="text-sm font-medium {marketStatus.is_open ? 'text-green-600' : 'text-gray-500'}">
							{marketStatus.is_open ? '🟢 Market Open' : '🔴 Market Closed'}
						</div>
					</div>
					<div class="grid grid-cols-1 gap-4">
						<!-- Trend Analysis Table -->
						<div class="bg-white rounded-lg border border-gray-200 overflow-hidden">
							<div class="overflow-x-auto">
								<table class="w-full">
									<thead class="bg-gray-50">
										<tr>
											<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Indicator</th>
											<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Trend</th>
											<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">T.frame</th>
											<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">7 MA</th>
											<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">20 MA</th>
											<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Last Changed</th>
										</tr>
									</thead>
									<tbody class="divide-y divide-gray-200">
										<!-- Major Trend Row -->
										<tr class="hover:bg-gray-50">
											<td class="px-4 py-3">
												<div class="flex items-center gap-2">
													<div class="w-3 h-3 {getTrendDotColor(engineStatus.major_trend)} rounded-full"></div>
													<span class="text-sm font-medium text-gray-900">Major</span>
												</div>
											</td>
											<td class="px-4 py-3">
												<span class="px-2 py-1 text-xs font-semibold rounded-full {getTrendColor(engineStatus.major_trend)} bg-opacity-10">
													{formatTrend(engineStatus.major_trend)}
												</span>
											</td>
											<td class="px-4 py-3 text-sm text-gray-700">
												{engineStatus.major_timeframe}
											</td>
											<td class="px-4 py-3 text-sm text-right font-medium text-gray-900">
												{engineStatus.major_ma7 ? engineStatus.major_ma7.toFixed(2) : '-'}
											</td>
											<td class="px-4 py-3 text-sm text-right font-medium text-gray-900">
												{engineStatus.major_ma20 ? engineStatus.major_ma20.toFixed(2) : '-'}
											</td>
											<td class="px-4 py-3 text-sm text-gray-700">
												{engineStatus.major_trend_changed_at ? formatTime(engineStatus.major_trend_changed_at) : '-'}
											</td>
										</tr>
										<!-- Minor Trend Row -->
										<tr class="hover:bg-gray-50">
											<td class="px-4 py-3">
												<div class="flex items-center gap-2">
													<div class="w-3 h-3 {getTrendDotColor(engineStatus.minor_trend)} rounded-full"></div>
													<span class="text-sm font-medium text-gray-900">Minor</span>
												</div>
											</td>
											<td class="px-4 py-3">
												<span class="px-2 py-1 text-xs font-semibold rounded-full {getTrendColor(engineStatus.minor_trend)} bg-opacity-10">
													{formatTrend(engineStatus.minor_trend)}
												</span>
											</td>
											<td class="px-4 py-3 text-sm text-gray-700">
												{engineStatus.minor_timeframe}
											</td>
											<td class="px-4 py-3 text-sm text-right font-medium text-gray-900">
												{engineStatus.minor_ma7 ? engineStatus.minor_ma7.toFixed(2) : '-'}
											</td>
											<td class="px-4 py-3 text-sm text-right font-medium text-gray-900">
												{engineStatus.minor_ma20 ? engineStatus.minor_ma20.toFixed(2) : '-'}
											</td>
											<td class="px-4 py-3 text-sm text-gray-700">
												{engineStatus.minor_trend_changed_at ? formatTime(engineStatus.minor_trend_changed_at) : '-'}
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</div>
						
						<!-- Trading Information Tabs -->
						<div class="bg-white rounded-lg border border-gray-200 overflow-hidden">
							<!-- Tab Headers -->
							<div class="border-b border-gray-200 bg-gray-50">
								<div class="flex">
									<button
										on:click={() => tradingInfoTab = 'instruments'}
										class="flex-1 px-4 py-3 text-sm font-medium transition-colors {tradingInfoTab === 'instruments' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
									>
										Instruments ({instruments.length})
									</button>
									<button
										on:click={() => tradingInfoTab = 'open-orders'}
										class="flex-1 px-4 py-3 text-sm font-medium transition-colors {tradingInfoTab === 'open-orders' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
									>
										Open Orders ({activeTrades.length})
									</button>
									<button
										on:click={() => tradingInfoTab = 'closed-orders'}
										class="flex-1 px-4 py-3 text-sm font-medium transition-colors {tradingInfoTab === 'closed-orders' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
									>
										Closed Orders ({closedTrades.length})
									</button>
									<button
										on:click={() => tradingInfoTab = 'positions'}
										class="flex-1 px-4 py-3 text-sm font-medium transition-colors {tradingInfoTab === 'positions' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
									>
										Positions ({engineStatus.active_positions || 0})
									</button>
								</div>
							</div>

							<!-- Tab Content -->
							<div class="max-h-64 overflow-y-auto">
								{#if tradingInfoTab === 'instruments'}
									<!-- Instruments Tab -->
									{#if instruments.length === 0}
										<div class="text-center py-8 text-gray-500 text-sm">
											No instruments available
										</div>
									{:else}
										<table class="w-full">
											<thead class="bg-gray-50 sticky top-0">
												<tr>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Type</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Symbol</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Strike</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">LTP</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Qty</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Value</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Cash After</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Triggers</th>
												</tr>
											</thead>
											<tbody class="divide-y divide-gray-200">
												{#each instruments as instrument}
													<tr class="hover:bg-gray-50 {instrument.type === 'INDEX' ? 'bg-blue-50' : ''}">
														<td class="px-3 py-2">
															{#if instrument.type === 'INDEX'}
																<span class="px-1.5 py-0.5 text-xs font-semibold rounded bg-blue-100 text-blue-700">
																	INDEX
																</span>
															{:else if instrument.type === 'CE'}
																<span class="px-1.5 py-0.5 text-xs font-semibold rounded bg-green-100 text-green-700">
																	CE
																</span>
															{:else if instrument.type === 'PE'}
																<span class="px-1.5 py-0.5 text-xs font-semibold rounded bg-red-100 text-red-700">
																	PE
																</span>
															{/if}
														</td>
														<td class="px-3 py-2 text-xs font-medium text-gray-900" title={instrument.tradingsymbol}>
															{instrument.symbol}
														</td>
														<td class="px-3 py-2 text-xs text-right text-gray-700">
															{instrument.strike ? instrument.strike : '-'}
														</td>
														<td class="px-3 py-2 text-xs text-right font-medium text-gray-900">
															{instrument.ltp ? formatCurrency(instrument.ltp) : '-'}
														</td>
														<td class="px-3 py-2 text-xs text-right text-gray-700">
															{instrument.expected_quantity || '-'}
														</td>
														<td class="px-3 py-2 text-xs text-right text-gray-700">
															{instrument.position_value ? formatCurrency(instrument.position_value) : '-'}
														</td>
														<td class="px-3 py-2 text-xs text-right text-gray-700">
															{instrument.cash_balance_after ? formatCurrency(instrument.cash_balance_after) : '-'}
														</td>
														<td class="px-3 py-2 text-xs text-gray-700">
															{#if instrument.entry_triggers && instrument.entry_triggers.length > 0}
																{#if instrument.entry_triggers.includes('SUSPENDED')}
																	<span class="px-1.5 py-0.5 text-xs font-semibold rounded bg-gray-200 text-gray-600">
																		SUSPENDED
																	</span>
																{:else}
																	<span class="text-xs text-gray-600">
																		{instrument.entry_triggers.join(', ')}
																	</span>
																{/if}
															{:else}
																-
															{/if}
														</td>
													</tr>
												{/each}
											</tbody>
										</table>
									{/if}
								{:else if tradingInfoTab === 'open-orders'}
									<!-- Open Orders Tab -->
									{#if activeTrades.length === 0}
										<div class="text-center py-8 text-gray-500 text-sm">
											No open orders
										</div>
									{:else}
										<table class="w-full">
											<thead class="bg-gray-50">
												<tr>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Time</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Instrument</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Type</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Qty</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Price</th>
												</tr>
											</thead>
											<tbody class="divide-y divide-gray-200">
												{#each activeTrades.slice(0, 5) as trade}
													<tr class="hover:bg-gray-50">
														<td class="px-3 py-2 text-xs text-gray-700">{formatTime(trade.entry_time)}</td>
														<td class="px-3 py-2 text-xs font-medium text-gray-900">{trade.instrument}</td>
														<td class="px-3 py-2">
															<span class="px-1.5 py-0.5 text-xs font-semibold rounded {trade.option_type === 'CE' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">
																{trade.option_type}
															</span>
														</td>
														<td class="px-3 py-2 text-xs text-right text-gray-700">{trade.quantity}</td>
														<td class="px-3 py-2 text-xs text-right text-gray-700">{formatCurrency(trade.entry_price)}</td>
													</tr>
												{/each}
											</tbody>
										</table>
									{/if}
								{:else if tradingInfoTab === 'closed-orders'}
									<!-- Closed Orders Tab -->
									{#if closedTrades.length === 0}
										<div class="text-center py-8 text-gray-500 text-sm">
											No closed orders
										</div>
									{:else}
										<table class="w-full">
											<thead class="bg-gray-50">
												<tr>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Entry</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Exit</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Instrument</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Type</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">P&L</th>
												</tr>
											</thead>
											<tbody class="divide-y divide-gray-200">
												{#each closedTrades.slice(0, 5) as trade}
													<tr class="hover:bg-gray-50">
														<td class="px-3 py-2 text-xs text-gray-700">{formatTime(trade.entry_time)}</td>
														<td class="px-3 py-2 text-xs text-gray-700">{formatTime(trade.exit_time)}</td>
														<td class="px-3 py-2 text-xs font-medium text-gray-900">{trade.instrument}</td>
														<td class="px-3 py-2">
															<span class="px-1.5 py-0.5 text-xs font-semibold rounded {trade.option_type === 'CE' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">
																{trade.option_type}
															</span>
														</td>
														<td class="px-3 py-2 text-xs text-right font-bold {getPnLColor(trade.pnl)}">
															{formatCurrency(trade.pnl)}
														</td>
													</tr>
												{/each}
											</tbody>
										</table>
									{/if}
								{:else if tradingInfoTab === 'positions'}
									<!-- Open Positions Tab -->
									{#if activeTrades.length === 0}
										<div class="text-center py-8 text-gray-500 text-sm">
											No open positions
										</div>
									{:else}
										<table class="w-full">
											<thead class="bg-gray-50">
												<tr>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Time</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Instrument</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Type</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Entry</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Current</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">P&L</th>
												</tr>
											</thead>
											<tbody class="divide-y divide-gray-200">
												{#each activeTrades.slice(0, 5) as trade}
													<tr class="hover:bg-gray-50">
														<td class="px-3 py-2 text-xs text-gray-700">{formatTime(trade.entry_time)}</td>
														<td class="px-3 py-2 text-xs font-medium text-gray-900">{trade.instrument}</td>
														<td class="px-3 py-2">
															<span class="px-1.5 py-0.5 text-xs font-semibold rounded {trade.option_type === 'CE' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">
																{trade.option_type}
															</span>
														</td>
														<td class="px-3 py-2 text-xs text-right text-gray-700">{formatCurrency(trade.entry_price)}</td>
														<td class="px-3 py-2 text-xs text-right font-medium text-gray-900">{formatCurrency(trade.current_price || trade.entry_price)}</td>
														<td class="px-3 py-2 text-xs text-right font-bold {getPnLColor(trade.unrealized_pnl || 0)}">
															{formatCurrency(trade.unrealized_pnl || 0)}
														</td>
													</tr>
												{/each}
											</tbody>
										</table>
									{/if}
								{/if}
							</div>
						</div>
					</div>
				</div>

				<!-- Performance -->
				<div class="bg-white rounded-lg shadow-md p-6">
					<h2 class="text-xl font-bold mb-4">Performance</h2>
					<div class="overflow-x-auto">
						<table class="w-full border-collapse">
							<tbody>
								<!-- Trade Row -->
								<tr class="border-b border-gray-200">
									<td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50">Trade</td>
									<td class="px-4 py-3 text-right">
										<div class="text-sm text-gray-600 mb-1">Call</div>
										<div class="text-lg font-bold text-green-600">{performance.call_trades}</div>
									</td>
									<td class="px-4 py-3 text-right">
										<div class="text-sm text-gray-600 mb-1">Put</div>
										<div class="text-lg font-bold text-red-600">{performance.put_trades}</div>
									</td>
									<td class="px-4 py-3 text-right">
										<div class="text-sm text-gray-600 mb-1">Total</div>
										<div class="text-lg font-bold text-blue-600">{performance.total_trades}</div>
									</td>
								</tr>
								<!-- P&L Row -->
								<tr class="border-b border-gray-200">
									<td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50">P&L</td>
									<td class="px-4 py-3 text-right">
										<div class="text-sm text-gray-600 mb-1">Realized</div>
										<div class="text-lg font-bold {getPnLColor(performance.realized_pnl)}">{formatCurrency(performance.realized_pnl)}</div>
									</td>
									<td class="px-4 py-3 text-right">
										<div class="text-sm text-gray-600 mb-1">Unrealized</div>
										<div class="text-lg font-bold {getPnLColor(performance.unrealized_pnl)}">{formatCurrency(performance.unrealized_pnl)}</div>
									</td>
									<td class="px-4 py-3 text-right">
										<div class="text-sm text-gray-600 mb-1">Total</div>
										<div class="text-lg font-bold {getPnLColor(performance.total_pnl)}">{formatCurrency(performance.total_pnl)}</div>
									</td>
								</tr>
								<!-- Initial Capital Row -->
								<tr class="border-b border-gray-200">
									<td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50">Open bal</td>
									<td colspan="3" class="px-4 py-3 text-right">
										<div class="text-xl font-bold text-gray-900">{formatCurrency(engineStatus.initial_capital)}</div>
									</td>
								</tr>
								<!-- Available Capital Row -->
								<tr class="border-b border-gray-200">
									<td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50">Avl bal</td>
									<td colspan="3" class="px-4 py-3 text-right">
										<div class="text-xl font-bold text-blue-600">{formatCurrency(engineStatus.current_capital)}</div>
									</td>
								</tr>
								<!-- Win Rate Row -->
								<tr>
									<td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50">Win Rate</td>
									<td colspan="3" class="px-4 py-3 text-right">
										<div class="text-xl font-bold text-purple-600">{performance.win_rate}%</div>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>
		{/if}	<!-- Trades Tab -->
	{#if mainTab === 'trades'}
		<div class="bg-white rounded-lg shadow-md">
			<!-- Subtab Headers -->
			<div class="border-b border-gray-200">
				<div class="flex gap-1 p-2">
					<button
						on:click={() => activeTab = 'performance'}
						class="px-6 py-3 rounded-t-lg font-medium transition-colors {activeTab === 'performance' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
					>
						📊 Active Positions ({activeTrades.length})
					</button>
					<button
						on:click={() => activeTab = 'closed'}
						class="px-6 py-3 rounded-t-lg font-medium transition-colors {activeTab === 'closed' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
					>
						📝 Closed Trades ({closedTrades.length})
					</button>
					<button
						on:click={() => activeTab = 'alerts'}
						class="px-6 py-3 rounded-t-lg font-medium transition-colors {activeTab === 'alerts' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
					>
						🔔 Alerts ({alerts.length})
					</button>
				</div>
			</div>

			<!-- Subtab Content -->
			<div class="p-6">
				{#if activeTab === 'performance'}
					<!-- Active Positions -->
					{#if activeTrades.length === 0}
						<div class="text-center py-12 text-gray-500">
							No active positions
						</div>
					{:else}
						<div class="overflow-x-auto">
							<table class="w-full">
								<thead class="bg-gray-50">
									<tr>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Time</th>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Instrument</th>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Type</th>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Trigger</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">Entry</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">Current</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">Target</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">Stop Loss</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">Qty</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">P&L</th>
										<th class="px-4 py-3 text-center text-sm font-semibold text-gray-700">Action</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-gray-200">
									{#each activeTrades as trade}
										<tr class="hover:bg-gray-50">
											<td class="px-4 py-3 text-sm text-gray-700">{formatTime(trade.entry_time)}</td>
											<td class="px-4 py-3 text-sm font-medium text-gray-900">{trade.instrument}</td>
											<td class="px-4 py-3">
												<span class="px-2 py-1 text-xs font-semibold rounded {trade.option_type === 'CE' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">
													{trade.option_type}
												</span>
											</td>
											<td class="px-4 py-3 text-sm text-gray-700">{trade.entry_trigger?.toUpperCase() || '-'}</td>
											<td class="px-4 py-3 text-sm text-right text-gray-700">{formatCurrency(trade.entry_price)}</td>
											<td class="px-4 py-3 text-sm text-right font-medium text-gray-900">{formatCurrency(trade.current_price || trade.entry_price)}</td>
											<td class="px-4 py-3 text-sm text-right text-green-600">{formatCurrency(trade.target_price)}</td>
											<td class="px-4 py-3 text-sm text-right text-red-600">{formatCurrency(trade.stoploss_price)}</td>
											<td class="px-4 py-3 text-sm text-right text-gray-700">{trade.quantity}</td>
											<td class="px-4 py-3 text-sm text-right font-bold {getPnLColor(trade.unrealized_pnl || 0)}">
												{formatCurrency(trade.unrealized_pnl || 0)}
											</td>
											<td class="px-4 py-3 text-center">
												<button
													on:click={() => closePosition(trade.id)}
													class="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
												>
													Close
												</button>
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				{:else if activeTab === 'closed'}
					<!-- Closed Trades -->
					{#if closedTrades.length === 0}
						<div class="text-center py-12 text-gray-500">
							No closed trades yet
						</div>
					{:else}
						<div class="overflow-x-auto">
							<table class="w-full">
								<thead class="bg-gray-50">
									<tr>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Entry</th>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Exit</th>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Instrument</th>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Type</th>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Trigger</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">Entry Price</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">Exit Price</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">Qty</th>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Exit Reason</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">P&L</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">P&L %</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-gray-200">
									{#each closedTrades as trade}
										<tr class="hover:bg-gray-50">
											<td class="px-4 py-3 text-sm text-gray-700">{formatTime(trade.entry_time)}</td>
											<td class="px-4 py-3 text-sm text-gray-700">{formatTime(trade.exit_time)}</td>
											<td class="px-4 py-3 text-sm font-medium text-gray-900">{trade.instrument}</td>
											<td class="px-4 py-3">
												<span class="px-2 py-1 text-xs font-semibold rounded {trade.option_type === 'CE' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">
													{trade.option_type}
												</span>
											</td>
											<td class="px-4 py-3 text-sm text-gray-700">{trade.entry_trigger?.toUpperCase() || '-'}</td>
											<td class="px-4 py-3 text-sm text-right text-gray-700">{formatCurrency(trade.entry_price)}</td>
											<td class="px-4 py-3 text-sm text-right text-gray-700">{formatCurrency(trade.exit_price)}</td>
											<td class="px-4 py-3 text-sm text-right text-gray-700">{trade.quantity}</td>
											<td class="px-4 py-3">
												<span class="px-2 py-1 text-xs font-semibold rounded {
													trade.exit_reason === 'target' ? 'bg-green-100 text-green-700' :
													trade.exit_reason === 'stoploss' ? 'bg-red-100 text-red-700' :
													'bg-yellow-100 text-yellow-700'
												}">
													{trade.exit_reason}
												</span>
											</td>
											<td class="px-4 py-3 text-sm text-right font-bold {getPnLColor(trade.pnl)}">
												{formatCurrency(trade.pnl)}
											</td>
											<td class="px-4 py-3 text-sm text-right font-bold {getPnLColor(trade.pnl_percentage)}">
												{trade.pnl_percentage?.toFixed(2)}%
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				{:else if activeTab === 'alerts'}
					<!-- Alerts -->
					{#if alerts.length === 0}
						<div class="text-center py-12 text-gray-500">
							No alerts yet
						</div>
					{:else}
						<div class="space-y-2 max-h-96 overflow-y-auto">
							{#each alerts as alert}
								<div class="flex items-center gap-2 p-3 rounded-lg bg-gray-50">
									<div class="w-3 h-3 rounded-full {
										alert.alert_type === 'entry' ? 'bg-green-500' :
										alert.alert_type === 'exit' ? 'bg-blue-500' :
										alert.alert_type === 'error' ? 'bg-red-500' :
										'bg-gray-500'
									}"></div>
									<div class="text-sm font-medium text-gray-900">
										{formatTime(alert.timestamp)}: {alert.message}
									</div>
								</div>
							{/each}
						</div>
					{/if}
				{/if}
			</div>
		</div>
	{/if}

	<!-- Configurations Tab -->
</div>
