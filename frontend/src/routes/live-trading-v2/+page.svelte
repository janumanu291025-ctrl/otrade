<script>
	import { onMount, onDestroy } from 'svelte';
	import CandlestickChart from '$lib/components/CandlestickChart.svelte';
	import AdvancedChart from '$lib/components/AdvancedChart.svelte';
	
	// API Base URL
	const API_URL = 'http://localhost:8000/api/live-trading-v2';
	
	// Engine Status
	let engineStatus = {
		running: false,
		paused: false,
		config_id: null,
		config_name: '',
		contract_expiry: null,
		started_at: null,
		nifty_ltp: 0,
		nifty_change: 0,
		nifty_change_pct: 0,
		major_trend: '',
		major_ma7: null,
		major_ma20: null,
		major_lbb: null,
		major_ubb: null,
		major_trend_changed_at: null,
		minor_trend: '',
		minor_ma7: null,
		minor_ma20: null,
		minor_lbb: null,
		minor_ubb: null,
		minor_trend_changed_at: null,
		major_timeframe: '15min',
		minor_timeframe: '1min',
		suspend_ce: false,
		suspend_pe: false
	};
	
	// Exchange time tracking for live clock
	let exchangeTime = null;  // Last received exchange time
	let exchangeTimeReceived = null;  // When we received it (system time)
	let currentDisplayTime = '';  // Current displayed time (updated every second)
	let timeDelay = 0;  // Delay in milliseconds
	
	// Market Status
	let marketStatus = {
		is_open: false,
		current_time: '',
		is_trading_day: false,
		market_open_time: '09:15',
		market_close_time: '15:30'
	};
	
	// Funds
	let funds = {
		available: 0,
		allocated: 0,
		remaining: 0,
		utilization_pct: 0
	};
	
	// Performance Metrics
	let performance = {
		total_trades: 0,
		call_trades: 0,
		put_trades: 0,
		realized_pnl: 0,
		unrealized_pnl: 0,
		total_pnl: 0,
		win_rate: 0
	};
	
	// UI State
	let error = null;
	let loading = false;
	let activeTrades = [];
	let closedTrades = [];
	let orders = [];  // Broker orders
	let positions = [];  // Broker positions
	let alerts = [];
	let configs = [];
	let selectedConfig = null;
	let contractExpiry = '';  // Contract expiry filter for live trading
	let wsConnected = false;
	let showTokenExpiredModal = false;
	let instruments = [];  // Available instruments for trading
	let instrumentsDownloadStatus = {
		count: 0,
		last_download: null,
		downloaded_today: false
	};
	let availableExpiries = [];  // Next 6 expiry dates
	let downloadingInstruments = false;
	
	// Tab state
	let mainTab = 'dash';
	let activeTab = 'performance';
	let tradingInfoTab = 'instruments';
	let alertTab = 'system';
	
	// Polling interval and WebSocket
	let statusInterval = null;
	let marketDataInterval = null;
	let clockInterval = null;  // For updating the live clock
	let ws = null;
	let pollInterval = 5000;  // Default 5 seconds, will adjust based on market hours
	
	// Update display time every second
	function updateDisplayTime() {
		if (!exchangeTime || !exchangeTimeReceived) {
			currentDisplayTime = '';
			timeDelay = 0;
			return;
		}
		
		// Calculate elapsed time since we received exchange time
		const now = Date.now();
		const elapsed = now - exchangeTimeReceived;
		
		// Add elapsed time to exchange time
		const displayTime = new Date(exchangeTime.getTime() + elapsed);
		
		// Format as HH:MM:SS
		currentDisplayTime = displayTime.toTimeString().split(' ')[0];
		
		// Calculate delay (difference between system time and exchange time)
		timeDelay = now - displayTime.getTime();
	}
	
	// Auto-hide error after 2 seconds
	$: if (error) {
		setTimeout(() => {
			error = null;
		}, 2000);
	}
	
	onMount(async () => {
		await loadConfigs();
		await loadMarketStatus();
		await loadInstrumentsStatus();
		await loadAvailableExpiries();
		await updateMarketData();  // Get market data first (includes Nifty LTP)
		await updateStatus();       // Then update status (which calls loadInstruments)
		
		// Adjust polling based on market hours
		adjustPollingStrategy();
		
		// Start polling
		statusInterval = setInterval(updateStatus, pollInterval);
		marketDataInterval = setInterval(updateMarketData, 60000); // Market data every minute
		
		// Start clock update (every second)
		clockInterval = setInterval(updateDisplayTime, 1000);
		
		// Initialize WebSocket (will only connect if market is open and engine running)
		initWebSocket();
	});
	
	onDestroy(() => {
		if (statusInterval) {
			clearInterval(statusInterval);
		}
		if (marketDataInterval) {
			clearInterval(marketDataInterval);
		}
		if (clockInterval) {
			clearInterval(clockInterval);
		}
		if (ws) {
			ws.close();
		}
	});
	
	// Reactive: Reload instruments when selectedConfig changes
	$: if (selectedConfig) {
		loadInstruments();
	}
	
	function adjustPollingStrategy() {
		// Clear existing intervals
		if (statusInterval) clearInterval(statusInterval);
		if (marketDataInterval) clearInterval(marketDataInterval);
		
		if (marketStatus.is_open) {
			// Market hours: Fast polling for both status (2s) and market data (10s)
			// WebSocket handles real-time LTP updates, but we poll market-data for trends/indicators
			pollInterval = 2000;
			statusInterval = setInterval(updateStatus, 2000);
			marketDataInterval = setInterval(updateMarketData, 10000); // Update trends every 10 seconds
		} else {
			// Off-market hours: Slower polling (1 minute)
			pollInterval = 60000;
			statusInterval = setInterval(updateStatus, 60000);
			marketDataInterval = setInterval(updateMarketData, 60000);
		}
	}
	
	async function updateMarketData() {
		try {
			const response = await fetch(`${API_URL}/market-data`);
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			if (!response.ok) {
				console.error('Failed to fetch market data');
				return;
			}
			
			const data = await response.json();
			
			if (data.available) {
				// Update market status
				if (data.market_status) {
					const oldMarketOpen = marketStatus.is_open;
					marketStatus = data.market_status;
					
					// If market status changed, adjust polling strategy
					if (oldMarketOpen !== marketStatus.is_open) {
						adjustPollingStrategy();
						
						// Reconnect WebSocket if market opened
						if (marketStatus.is_open && engineStatus.running) {
							initWebSocket();
						}
					}
				}
				
				// Update Nifty data
				if (data.nifty) {
					engineStatus.nifty_ltp = data.nifty.ltp;
					engineStatus.nifty_change = data.nifty.change;
					engineStatus.nifty_change_pct = data.nifty.change_pct;
					
					// Update exchange time for clock
					if (data.nifty.exchange_timestamp) {
						exchangeTime = new Date(data.nifty.exchange_timestamp);
						exchangeTimeReceived = Date.now();
						updateDisplayTime();
					}
				}
				
				// Update trends
				if (data.trends) {
					if (data.trends.major) {
						engineStatus.major_trend = data.trends.major.trend;
						engineStatus.major_ma7 = data.trends.major.ma7;
						engineStatus.major_ma20 = data.trends.major.ma20;
						engineStatus.major_trend_changed_at = data.trends.major.trend_changed_at;
						engineStatus.major_timeframe = data.trends.major.timeframe;
					}
					
					if (data.trends.minor) {
						engineStatus.minor_trend = data.trends.minor.trend;
						engineStatus.minor_ma7 = data.trends.minor.ma7;
						engineStatus.minor_ma20 = data.trends.minor.ma20;
						engineStatus.minor_trend_changed_at = data.trends.minor.trend_changed_at;
						engineStatus.minor_timeframe = data.trends.minor.timeframe;
					}
				}
			}
		} catch (err) {
			console.error('Error fetching market data:', err);
		}
	}
	
	async function updateStatus() {
		try {
			const response = await fetch(`${API_URL}/status`);
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			if (!response.ok) {
				const data = await response.json();
				if (!data.running) {
					engineStatus.running = false;
					return;
				}
				throw new Error(data.detail || 'Failed to fetch status');
			}
			
		const data = await response.json();
		
		// Preserve data from market data endpoint (which is more comprehensive)
		// Status endpoint should only update engine-specific fields
		const preservedNiftyLtp = engineStatus.nifty_ltp;
		const preservedNiftyChange = engineStatus.nifty_change;
		const preservedNiftyChangePct = engineStatus.nifty_change_pct;
		const preservedMajorTrend = engineStatus.major_trend;
		const preservedMajorMa7 = engineStatus.major_ma7;
		const preservedMajorMa20 = engineStatus.major_ma20;
		const preservedMajorLbb = engineStatus.major_lbb;
		const preservedMajorUbb = engineStatus.major_ubb;
		const preservedMajorTrendChangedAt = engineStatus.major_trend_changed_at;
		const preservedMinorTrend = engineStatus.minor_trend;
		const preservedMinorMa7 = engineStatus.minor_ma7;
		const preservedMinorMa20 = engineStatus.minor_ma20;
		const preservedMinorLbb = engineStatus.minor_lbb;
		const preservedMinorUbb = engineStatus.minor_ubb;
		const preservedMinorTrendChangedAt = engineStatus.minor_trend_changed_at;
		
		// Update engine status - only overwrite if new data is actually provided
		engineStatus = {
			running: data.running || false,
			paused: data.paused || false,
			config_id: data.config_id,
			config_name: data.config_name || '',
			contract_expiry: data.contract_expiry,
			started_at: data.started_at,
			// NIFTY data - prefer data from response if available, otherwise preserve
			nifty_ltp: (data.nifty_ltp && data.nifty_ltp > 0) ? data.nifty_ltp : preservedNiftyLtp || 0,
			nifty_change: (data.nifty_change !== undefined && data.nifty_change !== null) ? data.nifty_change : preservedNiftyChange,
			nifty_change_pct: (data.nifty_change_pct !== undefined && data.nifty_change_pct !== null) ? data.nifty_change_pct : preservedNiftyChangePct,
			// Major trend - preserve existing if not in response
			major_trend: data.major_trend || preservedMajorTrend || '',
			major_ma7: (data.major_ma7 !== undefined && data.major_ma7 !== null) ? data.major_ma7 : preservedMajorMa7,
			major_ma20: (data.major_ma20 !== undefined && data.major_ma20 !== null) ? data.major_ma20 : preservedMajorMa20,
			major_lbb: (data.major_lbb !== undefined && data.major_lbb !== null) ? data.major_lbb : preservedMajorLbb,
			major_ubb: (data.major_ubb !== undefined && data.major_ubb !== null) ? data.major_ubb : preservedMajorUbb,
			major_trend_changed_at: data.major_trend_changed_at || preservedMajorTrendChangedAt,
			// Minor trend - preserve existing if not in response
			minor_trend: data.minor_trend || preservedMinorTrend || '',
			minor_ma7: (data.minor_ma7 !== undefined && data.minor_ma7 !== null) ? data.minor_ma7 : preservedMinorMa7,
			minor_ma20: (data.minor_ma20 !== undefined && data.minor_ma20 !== null) ? data.minor_ma20 : preservedMinorMa20,
			minor_lbb: (data.minor_lbb !== undefined && data.minor_lbb !== null) ? data.minor_lbb : preservedMinorLbb,
			minor_ubb: (data.minor_ubb !== undefined && data.minor_ubb !== null) ? data.minor_ubb : preservedMinorUbb,
			minor_trend_changed_at: data.minor_trend_changed_at || preservedMinorTrendChangedAt,
			major_timeframe: data.major_timeframe || engineStatus.major_timeframe || '15min',
			minor_timeframe: data.minor_timeframe || engineStatus.minor_timeframe || '1min',
			suspend_ce: data.suspend_ce || false,
			suspend_pe: data.suspend_pe || false
		};			// Update funds
			if (data.funds) {
				funds = data.funds;
			}
			
			// Update performance
			if (data.pnl) {
				performance.realized_pnl = data.pnl.realized || 0;
				performance.unrealized_pnl = data.pnl.unrealized || 0;
				performance.total_pnl = data.pnl.total || 0;
			}
			
			if (data.trades) {
				performance.total_trades = data.trades.today || 0;
			}
			
			// Load additional data - always load to show broker data during off-market hours
			// During off-market, backend returns broker positions/orders even if engine not running
			await loadTrades();
			await loadOrders();
			await loadPositions();
			await loadAlerts();
			await loadInstruments();  // Always load instruments to show potential trades
		} catch (err) {
			console.error('Error fetching status:', err);
		}
	}
	
	async function loadConfigs() {
		try {
			const response = await fetch('http://localhost:8000/api/config/');
			const data = await response.json();
			configs = data.configs || [];
			if (configs.length > 0 && !selectedConfig) {
				selectedConfig = configs[0].id;
			}
		} catch (err) {
			console.error('Error loading configs:', err);
		}
	}
	
	async function loadMarketStatus() {
		try {
			const response = await fetch('http://localhost:8000/api/market-time/status');
			const result = await response.json();
			// Updated to handle the correct response format from market-time API
			marketStatus = result;
		} catch (err) {
			console.error('Error loading market status:', err);
		}
	}
	
	async function loadInstrumentsStatus() {
		try {
			const response = await fetch('http://localhost:8000/api/broker/instruments/status/kite');
			const data = await response.json();
			instrumentsDownloadStatus = {
				count: data.count || 0,
				last_download: data.last_download,
				downloaded_today: data.downloaded_today || false
			};
		} catch (err) {
			console.error('Error loading instruments status:', err);
		}
	}
	
	async function loadAvailableExpiries() {
		try {
			// Get all NFO instruments with expiry dates
			const response = await fetch('http://localhost:8000/api/broker/instruments?exchange=NFO&instrument_type=CE&limit=10000');
			
			if (!response.ok) {
				console.error('Failed to fetch instruments for expiries:', response.statusText);
				return;
			}
			
		const data = await response.json();
		
		if (!data.data || data.data.length === 0) {
			console.log('No instruments found for expiry dates');
			return;
		}
		
		// Extract unique expiry dates
		const expiries = new Set();
		data.data.forEach(inst => {
			if (inst.expiry) {
				expiries.add(inst.expiry);
			}
		});			// Sort and get next 6 expiries
			const sortedExpiries = Array.from(expiries).sort();
			const today = new Date();
			const futureExpiries = sortedExpiries.filter(exp => {
				const expDate = new Date(exp);
				return expDate >= today;
			});
			
			availableExpiries = futureExpiries.slice(0, 6);
			console.log('Loaded available expiries:', availableExpiries);
		} catch (err) {
			console.error('Error loading available expiries:', err);
		}
	}
	
	async function loadInstruments() {
		try {
			// Determine which config to use
			let configId = engineStatus.config_id;
			
			// If engine not running, use selected config or first available config
			if (!configId) {
				if (selectedConfig) {
					configId = selectedConfig;
				} else if (configs.length > 0) {
					configId = configs[0].id;
				}
			}
			
			if (!configId) {
				console.log('Cannot load instruments: No config available');
				return;
			}
			
			// Call backend API to get instruments based on trading logic
			// Add timestamp to prevent caching
			const response = await fetch(`${API_URL}/instruments/${configId}?_t=${Date.now()}`);
			const result = await response.json();
			
			if (result.status === 'success') {
				instruments = result.instruments || [];
				console.log('Loaded instruments:', instruments.map(i => ({
					type: i.type,
					ltp: i.ltp,
					qty: i.expected_quantity,
					value: i.position_value
				})));
			} else {
				console.error('Failed to load instruments:', result);
				instruments = [];
			}
		} catch (err) {
			console.error('Error loading instruments:', err);
			// Show at least Nifty 50 even if there's an error
			if (engineStatus.nifty_ltp && engineStatus.nifty_ltp > 0) {
				instruments = [{
					type: 'INDEX',
					symbol: 'NIFTY 50',
					tradingsymbol: 'NIFTY 50',
					strike: null,
					ltp: engineStatus.nifty_ltp,
					expected_quantity: null,
					position_value: null,
					cash_balance_after: funds.remaining,
					entry_triggers: []
				}];
			}
		}
	}
	
	async function downloadInstruments() {
		if (!confirm('Download latest instruments from broker? This will take a few moments.')) {
			return;
		}
		
		downloadingInstruments = true;
		error = null;
		
		try {
			const response = await fetch('http://localhost:8000/api/broker/instruments/download/kite', {
				method: 'POST'
			});
			
			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || 'Failed to download instruments');
			}
			
			const result = await response.json();
			alert(`Successfully downloaded ${result.count} instruments!`);
			
			// Reload status and expiries
			await loadInstrumentsStatus();
			await loadAvailableExpiries();
		} catch (err) {
			error = err.message || 'Failed to download instruments';
			console.error('Error downloading instruments:', err);
		} finally {
			downloadingInstruments = false;
		}
	}
	
	async function loadTrades() {
		try {
			// Fetch executed orders/trades from broker via centralized orders API
			const response = await fetch(`${API_URL}/orders`);
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			// If no orders available
			if (response.status === 404 || response.status === 204) {
				activeTrades = [];
				closedTrades = [];
				return;
			}
			
			const data = await response.json();
			const orders = data.data || [];
			
			// Filter orders by execution status
			// Active: pending, open orders
			// Closed: executed, cancelled, rejected orders
			activeTrades = orders.filter(o => 
				['pending', 'open', 'trigger pending'].includes(o.status?.toLowerCase())
			);
			closedTrades = orders.filter(o => 
				['complete', 'cancelled', 'rejected', 'expired'].includes(o.status?.toLowerCase())
			);
			
			// Calculate performance metrics from executed trades
			const executedTrades = orders.filter(o => o.status?.toLowerCase() === 'complete');
			performance.total_trades = executedTrades.length;
			performance.call_trades = executedTrades.filter(o => o.instrument_type === 'CE').length;
			performance.put_trades = executedTrades.filter(o => o.instrument_type === 'PE').length;
			
			// Calculate win rate based on orders marked for tracking
			const trackedOrders = executedTrades.filter(o => o.pnl !== undefined);
			const winners = trackedOrders.filter(o => o.pnl > 0);
			performance.win_rate = trackedOrders.length > 0
				? (winners.length / trackedOrders.length * 100).toFixed(1)
				: 0;
		} catch (err) {
			console.error('Error loading trades:', err);
		}
	}
	
	async function loadAlerts() {
		if (!engineStatus.config_id) return;
		
		try {
			const response = await fetch(`${API_URL}/alerts?limit=100`);
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			const data = await response.json();
			alerts = (data.alerts || []).slice(0, 100);
		} catch (err) {
			console.error('Error loading alerts:', err);
		}
	}
	
	async function loadOrders() {
		try {
			// Use consolidated GET /api/orders endpoint
			const response = await fetch('http://localhost:8000/api/orders');
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			// If engine not running or no orders, that's okay
			if (response.status === 404) {
				orders = [];
				return;
			}
			
			const data = await response.json();
			// New API returns {status, data, count} format
			orders = data.data || data.orders || [];
		} catch (err) {
			console.error('Error loading orders:', err);
			orders = [];
		}
	}
	
	async function loadPositions() {
		try {
			// Use consolidated portfolio API for positions (net and day)
			const response = await fetch('http://localhost:8000/api/portfolio/positions');
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			// If no data available
			if (response.status === 404) {
				positions = [];
				return;
			}
			
			const data = await response.json();
			// Extract net positions from the consolidated response
			const positionsData = data.data || {};
			positions = positionsData.net || [];
		} catch (err) {
			console.error('Error loading positions:', err);
			positions = [];
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
			let url = `${API_URL}/start?config_id=${selectedConfig}`;
			if (contractExpiry) {
				url += `&contract_expiry=${contractExpiry}`;
			}
			
			const response = await fetch(url, { method: 'POST' });
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
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
		if (!confirm('Are you sure you want to stop live trading? All positions will be squared off.')) {
			return;
		}
		
		loading = true;
		error = null;
		
		try {
			const response = await fetch(`${API_URL}/stop`, { method: 'POST' });
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to stop engine');
			}
			
			await updateStatus();
		} catch (err) {
			error = err.message || 'Failed to stop engine';
			console.error('Error stopping engine:', err);
		} finally {
			loading = false;
		}
	}
	
	async function pauseEngine() {
		loading = true;
		error = null;
		
		try {
			const response = await fetch(`${API_URL}/pause`, { method: 'POST' });
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to pause engine');
			}
			
			await updateStatus();
		} catch (err) {
			error = err.message || 'Failed to pause engine';
			console.error('Error pausing engine:', err);
		} finally {
			loading = false;
		}
	}
	
	async function resumeEngine() {
		loading = true;
		error = null;
		
		try {
			const response = await fetch(`${API_URL}/resume`, { method: 'POST' });
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to resume engine');
			}
			
			await updateStatus();
		} catch (err) {
			error = err.message || 'Failed to resume engine';
			console.error('Error resuming engine:', err);
		} finally {
			loading = false;
		}
	}
	
	async function toggleSuspendCE(suspend) {
		try {
			const response = await fetch(`${API_URL}/suspend-ce`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ suspend })
			});
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			await updateStatus();
		} catch (err) {
			error = err.message || 'Failed to toggle CE suspension';
			console.error('Error toggling CE:', err);
		}
	}
	
	async function toggleSuspendPE(suspend) {
		try {
			const response = await fetch(`${API_URL}/suspend-pe`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ suspend })
			});
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			await updateStatus();
		} catch (err) {
			error = err.message || 'Failed to toggle PE suspension';
			console.error('Error toggling PE:', err);
		}
	}
	
	async function closePosition(tradeId) {
		if (!confirm('Are you sure you want to close this position?')) return;
		
		try {
			const response = await fetch(`${API_URL}/close-position`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ trade_id: tradeId, reason: 'manual_close' })
			});
			
			if (response.status === 401) {
				showTokenExpiredModal = true;
				return;
			}
			
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to close position');
			}
			
			await loadTrades();
		} catch (err) {
			error = err.message || 'Failed to close position';
			console.error('Error closing position:', err);
		}
	}
	
	// Order management functions (using consolidated API)
	async function cancelOrder(orderId, variety = 'regular') {
		if (!confirm('Are you sure you want to cancel this order?')) {
			return;
		}
		
		try {
			// Use consolidated DELETE /api/orders/:variety/:order_id endpoint
			const response = await fetch(`http://localhost:8000/api/orders/${variety}/${orderId}`, {
				method: 'DELETE'
			});
			
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to cancel order');
			}
			
			// Reload orders
			await loadOrders();
			alert('Order cancelled successfully');
		} catch (err) {
			error = err.message || 'Failed to cancel order';
			alert('Error: ' + error);
			console.error('Error canceling order:', err);
		}
	}
	
	let modifyOrderId = null;
	let modifyPrice = 0;
	let showModifyModal = false;
	
	// Manual order placement state
	let showManualOrderModal = false;
	let manualOrder = {
		tradingsymbol: '',
		exchange: 'NFO',
		transaction_type: 'BUY',
		quantity: 15,
		order_type: 'LIMIT',
		product: 'MIS',
		price: null,
		trigger_price: null,
		validity: 'DAY'
	};
	
	function openManualOrderModal() {
		// Reset form
		manualOrder = {
			tradingsymbol: '',
			exchange: 'NFO',
			transaction_type: 'BUY',
			quantity: 15,
			order_type: 'LIMIT',
			product: 'MIS',
			price: null,
			trigger_price: null,
			validity: 'DAY'
		};
		showManualOrderModal = true;
	}
	
	async function placeManualOrder() {
		// Validation
		if (!manualOrder.tradingsymbol) {
			alert('Please enter trading symbol');
			return;
		}
		if (!manualOrder.quantity || manualOrder.quantity <= 0) {
			alert('Please enter valid quantity');
			return;
		}
		if (manualOrder.order_type === 'LIMIT' && (!manualOrder.price || manualOrder.price <= 0)) {
			alert('Please enter valid price for LIMIT order');
			return;
		}
		if ((manualOrder.order_type === 'SL' || manualOrder.order_type === 'SL-M') && (!manualOrder.trigger_price || manualOrder.trigger_price <= 0)) {
			alert('Please enter valid trigger price for SL/SL-M order');
			return;
		}
		
		try {
			// Use consolidated POST /api/orders/:variety endpoint with JSON body
			const orderData = {
				tradingsymbol: manualOrder.tradingsymbol.toUpperCase(),
				exchange: manualOrder.exchange,
				transaction_type: manualOrder.transaction_type,
				quantity: manualOrder.quantity,
				order_type: manualOrder.order_type,
				product: manualOrder.product,
				validity: manualOrder.validity
			};
			
			if (manualOrder.price) {
				orderData.price = parseFloat(manualOrder.price);
			}
			if (manualOrder.trigger_price) {
				orderData.trigger_price = parseFloat(manualOrder.trigger_price);
			}
			
			const response = await fetch(`http://localhost:8000/api/orders/regular`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(orderData)
			});
			
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to place order');
			}
			
			const result = await response.json();
			showManualOrderModal = false;
			await loadOrders();
			alert('Order placed successfully! Order ID: ' + (result.data?.order_id || 'N/A'));
		} catch (err) {
			error = err.message || 'Failed to place order';
			alert('Error: ' + error);
			console.error('Error placing manual order:', err);
		}
	}
	
	function openModifyOrderModal(order) {
		modifyOrderId = order.order_id;
		modifyPrice = order.price;
		showModifyModal = true;
	}
	
	async function modifyOrder(variety = 'regular') {
		if (!modifyOrderId || !modifyPrice) return;
		
		try {
			// Use consolidated PUT /api/orders/:variety/:order_id endpoint with JSON body
			const modifyData = {
				price: parseFloat(modifyPrice)
			};
			
			const response = await fetch(`http://localhost:8000/api/orders/${variety}/${modifyOrderId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(modifyData)
			});
			
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to modify order');
			}
			
			showModifyModal = false;
			await loadOrders();
			alert('Order modified successfully');
		} catch (err) {
			error = err.message || 'Failed to modify order';
			alert('Error: ' + error);
			console.error('Error modifying order:', err);
		}
	}

async function closeBrokerPosition(position) {
	if (!confirm(`Are you sure you want to close position: ${position.instrument || position.tradingsymbol}?`)) {
		return;
	}
	
	try {
		const response = await fetch('http://localhost:8000/api/broker/positions/close', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				tradingsymbol: position.instrument || position.tradingsymbol,
				exchange: position.exchange
			})
		});			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || 'Failed to close position');
			}
			
			await loadPositions();
		} catch (err) {
			error = err.message || 'Failed to close position';
			console.error('Error closing position:', err);
		}
	}
	
	function initWebSocket() {
		// Only connect WebSocket if market is open
		if (!marketStatus.is_open) {
			console.log('Market closed - WebSocket not needed');
			return;
		}
		
		// Close existing connection
		if (ws) {
			ws.close();
		}
		
		try {
			ws = new WebSocket('ws://localhost:8000/ws');
			
			ws.onopen = () => {
				console.log('WebSocket connected');
				wsConnected = true;
			};
			
			ws.onmessage = (event) => {
				try {
					const message = JSON.parse(event.data);
					handleWebSocketMessage(message);
				} catch (error) {
					console.error('Error parsing WebSocket message:', error);
				}
			};
			
			ws.onerror = (error) => {
				console.error('WebSocket error:', error);
				wsConnected = false;
			};
			
			ws.onclose = () => {
				console.log('WebSocket disconnected');
				wsConnected = false;
				
				// Only reconnect if market is still open
				if (marketStatus.is_open) {
					setTimeout(initWebSocket, 5000);
				}
			};
		} catch (error) {
			console.error('Error initializing WebSocket:', error);
		}
	}
	
	function handleWebSocketMessage(message) {
		// Debug log all messages
		console.log('[WS] Received message:', message.type, message);
		
		switch (message.type) {
			case 'token_expired':
				showTokenExpiredModal = true;
				break;
			
			case 'market_data':
				// Real-time market data update from WebSocket (Kite format)
				console.log('[WS] Processing market_data:', message.data);
				if (message.data && Array.isArray(message.data)) {
					message.data.forEach(tick => {
						// Check for Nifty 50 (token 256265)
						if (tick.instrument_token === 256265) {
							// Kite sends prices as actual rupees (not paise) - use directly
							// Note: KiteTicker library already converts paise to rupees
							const ltpValue = tick.last_price;
							if (ltpValue && ltpValue > 0) {
								engineStatus.nifty_ltp = ltpValue;
								console.log(`✅ Nifty 50 LTP updated: ${ltpValue} (WebSocket)`);
							}
							
							// Calculate change if we have OHLC data
							if (tick.ohlc && tick.ohlc.close) {
								const change = ltpValue - tick.ohlc.close;
								const changePct = (change / tick.ohlc.close) * 100;
								engineStatus.nifty_change = change;
								engineStatus.nifty_change_pct = changePct;
							}
						}
					});
					
					// Refresh positions to get updated P&L with new LTPs
					if (engineStatus.running && message.data.length > 0) {
						// Debounce: only refresh every 2 seconds
						if (!window._lastPositionRefresh || Date.now() - window._lastPositionRefresh > 2000) {
							window._lastPositionRefresh = Date.now();
							loadTrades();
						}
					}
				}
				break;
			
			case 'ltp_update':
				// Legacy format - Real-time LTP update from WebSocket
				if (message.data && message.data.instrument_token === 256265) {
					// Nifty 50 update
					engineStatus.nifty_ltp = message.data.last_price;
					if (message.data.change) {
						engineStatus.nifty_change = message.data.change;
						engineStatus.nifty_change_pct = message.data.change_percent;
					}
				}
				// Refresh positions to get updated P&L
				if (engineStatus.running) {
					loadTrades();
				}
				break;
			
			case 'order_update':
				// Real-time order status update
				// Refresh positions and trades
				if (engineStatus.running) {
					updateStatus();
					loadTrades();
				}
				break;
			
			case 'alert':
				// New alert received
				if (engineStatus.running) {
					loadAlerts();
				}
				break;
			
			case 'trend_change':
				// Trend changed
				if (message.data) {
					if (message.data.timeframe === '15min') {
						engineStatus.major_trend = message.data.trend;
						engineStatus.major_trend_changed_at = message.data.changed_at;
					} else if (message.data.timeframe === '1min') {
						engineStatus.minor_trend = message.data.trend;
						engineStatus.minor_trend_changed_at = message.data.changed_at;
					}
				}
				break;
			
			default:
				console.log('Unknown WebSocket message type:', message.type);
		}
	}
	
	function handleTokenReauth() {
		// Redirect to authentication page
		window.location.href = '/settings?redirect=/live-trading-v2';
	}
	
	function formatCurrency(value) {
		return new Intl.NumberFormat('en-IN', {
			minimumFractionDigits: 0,
			maximumFractionDigits: 0
		}).format(value || 0);
	}
	
	function formatLTP(value) {
		return new Intl.NumberFormat('en-IN', {
			minimumFractionDigits: 2,
			maximumFractionDigits: 2
		}).format(value || 0);
	}
	
	function formatDateTime(dateStr) {
		if (!dateStr) return '-';
		const date = new Date(dateStr);
		const now = new Date();
		const diffMs = now - date;
		const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
		const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
		
		const day = date.getDate().toString().padStart(2, '0');
		const month = date.toLocaleString('en-IN', { month: 'short' });
		const year = date.getFullYear();
		const time = date.toLocaleTimeString('en-IN', { 
			hour: '2-digit', 
			minute: '2-digit', 
			second: '2-digit',
			hour12: true 
		});
		
		const timeAgo = `(${diffHours}:${diffMinutes.toString().padStart(2, '0')} hr ago)`;
		return `${day}-${month}-${year}, ${time} ${timeAgo}`;
	}
	
	function formatTime(dateStr) {
		if (!dateStr) return '-';
		return new Date(dateStr).toLocaleTimeString('en-IN');
	}
	
	function getStatusColor(running, paused) {
		if (!running) return 'text-gray-600 bg-gray-100';
		if (paused) return 'text-yellow-600 bg-yellow-100';
		return 'text-green-600 bg-green-100';
	}
	
	function getStatusText(running, paused) {
		if (!running) return 'STOPPED';
		if (paused) return 'PAUSED';
		return 'RUNNING';
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
			<h1 class="text-3xl font-bold text-gray-900">Live</h1>
		</div>
		<div class="flex items-center gap-3">
			<!-- WebSocket Status -->
			<div class="flex items-center gap-2 px-3 py-2 bg-white rounded-lg border">
				<div class="w-2 h-2 rounded-full {wsConnected ? 'bg-green-500' : 'bg-red-500'}"></div>
				<span class="text-sm text-gray-600">
					{wsConnected ? 'Connected' : 'Disconnected'}
				</span>
			</div>
			<!-- Status Badge -->
			<div class="px-4 py-2 rounded-lg {getStatusColor(engineStatus.running, engineStatus.paused)} font-semibold">
				{getStatusText(engineStatus.running, engineStatus.paused)}
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
			<button
				on:click={() => mainTab = 'charts'}
				class="px-6 py-3 rounded-t-lg font-medium transition-colors {mainTab === 'charts' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
			>
				📈 Charts
			</button>
		</div>
	</div>
	
	<!-- Error Display -->
	{#if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-3">
					<span class="text-red-600 text-xl">⚠️</span>
					<span class="text-red-700 font-medium">Error: {error}</span>
				</div>
				<button on:click={() => error = null} class="text-red-600 hover:text-red-800">✕</button>
			</div>
		</div>
	{/if}
	
	<!-- Token Expired Modal -->
	{#if showTokenExpiredModal}
		<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
			<div class="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
				<div class="flex items-start gap-4">
					<div class="flex-shrink-0">
						<div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
							<span class="text-2xl">🔒</span>
						</div>
					</div>
					<div class="flex-1">
						<h3 class="text-lg font-bold text-gray-900">Token Expired</h3>
						<p class="text-gray-600 mt-2">
							Your broker access token has expired. Please re-authenticate to continue live trading.
						</p>
						<div class="mt-6 flex gap-3">
							<button
								on:click={handleTokenReauth}
								class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold"
							>
								Re-authenticate
							</button>
							<button
								on:click={() => showTokenExpiredModal = false}
								class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
							>
								Cancel
							</button>
						</div>
					</div>
				</div>
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
				<div class="flex items-center gap-3 mb-2">
					<label for="config-select" class="text-sm font-bold text-gray-700">Configuration:</label>
					<select
						id="config-select"
						bind:value={selectedConfig}
						disabled={engineStatus.running}
						class="flex-1 px-3 py-2 border rounded-lg disabled:bg-gray-100 text-sm"
					>
						{#each configs as config}
							<option value={config.id}>{config.name}</option>
						{/each}
					</select>
					<a href="/config" class="px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 font-medium">
						Edit
					</a>
				</div>
				
				<!-- Config Summary -->
				{#if selectedConfig && configs.length > 0}
					{@const selectedConfigData = configs.find(c => c.id === selectedConfig)}
					{#if selectedConfigData}
						<div class="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
							<p class="text-xs font-semibold text-gray-700 mb-2">Configuration Summary</p>
							<div class="space-y-1 text-xs text-gray-600">
								<div class="flex justify-between">
									<span>Capital Allocation:</span>
									<span class="font-medium text-gray-900">{selectedConfigData.capital_allocation_pct}%</span>
								</div>
								<div class="flex justify-between">
									<span>Lot Size:</span>
									<span class="font-medium text-gray-900">{selectedConfigData.lot_size}</span>
								</div>
								<div class="flex justify-between">
									<span>Short MA:</span>
									<span class="font-medium text-gray-900">{selectedConfigData.ma_short_period || 7}</span>
								</div>
								<div class="flex justify-between">
									<span>Long MA:</span>
									<span class="font-medium text-gray-900">{selectedConfigData.ma_long_period || 20}</span>
								</div>
								<div class="flex justify-between">
									<span>Target:</span>
									<span class="font-medium text-gray-900">{selectedConfigData.buy_7ma_target_percentage || 2.5}% / {selectedConfigData.buy_20ma_target_percentage || 2.5}%</span>
								</div>
								<div class="flex justify-between">
									<span>Stoploss:</span>
									<span class="font-medium text-gray-900">{selectedConfigData.buy_7ma_stoploss_percentage || 99.0}% / {selectedConfigData.buy_20ma_stoploss_percentage || 99.0}%</span>
								</div>
								<div class="flex justify-between">
									<span>Squareoff Time:</span>
									<span class="font-medium text-gray-900">{selectedConfigData.square_off_time || '15:20'}</span>
								</div>
								{#if selectedConfigData.max_positions}
									<div class="flex justify-between">
										<span>Max Positions:</span>
										<span class="font-medium text-gray-900">{selectedConfigData.max_positions}</span>
									</div>
								{/if}
							</div>
						</div>
					{/if}
				{/if}
			</div>				<!-- Contract Expiry Filter (Live Trading Specific) -->
				{#if !engineStatus.running}
					<div class="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
						<label for="contract-expiry" class="block text-sm font-medium text-gray-900 mb-2">
							Contract Expiry Filter (Optional)
						</label>
						<select
							id="contract-expiry"
							bind:value={contractExpiry}
							class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
						>
							<option value="">Auto (Nearest Weekly)</option>
							{#each availableExpiries as expiry}
								<option value={expiry}>{new Date(expiry).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })}</option>
							{/each}
						</select>
						<p class="text-xs text-gray-600 mt-2">
							Select contract expiry date or leave as Auto for nearest weekly expiry.
						</p>
						
						<!-- Instrument Download Status -->
						<div class="mt-3 pt-3 border-t border-blue-300">
							<div class="flex items-center justify-between text-xs">
								<div>
									<span class="text-gray-700">Instruments: </span>
									<span class="font-semibold text-gray-900">{formatCurrency(instrumentsDownloadStatus.count)}</span>
									{#if instrumentsDownloadStatus.last_download}
										<div class="text-gray-600 mt-1 font-bold">
											Last updated: {formatDateTime(instrumentsDownloadStatus.last_download)}
										</div>
									{/if}
								</div>
								<button
									on:click={downloadInstruments}
									disabled={downloadingInstruments}
									class="px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 font-medium"
								>
									{downloadingInstruments ? 'Downloading...' : 'Update'}
								</button>
							</div>
						</div>
					</div>
				{:else if engineStatus.contract_expiry}
					<div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
						<div class="flex items-center gap-2">
							<span class="text-lg">📅</span>
							<div class="flex-1">
								<p class="text-sm font-medium text-blue-900">Contract Expiry</p>
								<p class="text-xs text-blue-700">{new Date(engineStatus.contract_expiry).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })}</p>
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
							▶ Start Live Trading
						</button>
					{:else if engineStatus.paused}
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
							⏹ Stop & Square Off
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
					<div class="flex items-center gap-4">
						<h2 class="text-xl font-bold">Nifty 50</h2>
						{#if engineStatus.nifty_ltp}
							<span class="text-2xl font-bold text-blue-600">
								{formatLTP(engineStatus.nifty_ltp)}
							</span>
							{#if engineStatus.nifty_change !== undefined}
								<span class="text-sm font-semibold {engineStatus.nifty_change >= 0 ? 'text-green-600' : 'text-red-600'}">
									{engineStatus.nifty_change >= 0 ? '▲' : '▼'}
									{Math.abs(engineStatus.nifty_change).toFixed(2)}
									({engineStatus.nifty_change_pct >= 0 ? '+' : ''}{engineStatus.nifty_change_pct?.toFixed(2)}%)
								</span>
							{/if}
						{/if}
					</div>
					<div class="flex items-center gap-3">
						{#if currentDisplayTime}
							<div class="text-sm font-mono text-gray-700 font-semibold">
								{currentDisplayTime}
								<span class="text-xs text-gray-500">
									({timeDelay > 0 ? '+' : ''}{(timeDelay / 1000).toFixed(timeDelay < 1000 ? 0 : 0)}{timeDelay >= 1000 ? 's' : 'ms'})
								</span>
							</div>
						{/if}
						<div class="text-sm font-medium {marketStatus.is_open ? 'text-green-600' : 'text-gray-500'}">
							{marketStatus.is_open ? '🟢 Market Open' : '🔴 Market Closed'}
						</div>
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
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">LTP-LBB</th>
										<th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">UBB-LTP</th>
										<th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Last Changed</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-gray-200">
									<!-- Minor Trend Row (shown first) -->
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
										<td class="px-4 py-3 text-sm text-right font-medium">
											{#if engineStatus.nifty_ltp && engineStatus.minor_lbb}
												<span class="{(engineStatus.nifty_ltp - engineStatus.minor_lbb) > 0 ? 'text-green-600' : 'text-red-600'}">
													{(engineStatus.nifty_ltp - engineStatus.minor_lbb).toFixed(2)}
												</span>
											{:else}
												<span class="text-gray-400">-</span>
											{/if}
										</td>
										<td class="px-4 py-3 text-sm text-right font-medium">
											{#if engineStatus.nifty_ltp && engineStatus.minor_ubb}
												<span class="{(engineStatus.minor_ubb - engineStatus.nifty_ltp) > 0 ? 'text-green-600' : 'text-red-600'}">
													{(engineStatus.minor_ubb - engineStatus.nifty_ltp).toFixed(2)}
												</span>
											{:else}
												<span class="text-gray-400">-</span>
											{/if}
										</td>
										<td class="px-4 py-3 text-sm text-gray-700">
											{engineStatus.minor_trend_changed_at ? formatTime(engineStatus.minor_trend_changed_at) : '-'}
										</td>
									</tr>
									<!-- Major Trend Row (shown second) -->
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
										<td class="px-4 py-3 text-sm text-right font-medium">
											{#if engineStatus.nifty_ltp && engineStatus.major_lbb}
												<span class="{(engineStatus.nifty_ltp - engineStatus.major_lbb) > 0 ? 'text-green-600' : 'text-red-600'}">
													{(engineStatus.nifty_ltp - engineStatus.major_lbb).toFixed(2)}
												</span>
											{:else}
												<span class="text-gray-400">-</span>
											{/if}
										</td>
										<td class="px-4 py-3 text-sm text-right font-medium">
											{#if engineStatus.nifty_ltp && engineStatus.major_ubb}
												<span class="{(engineStatus.major_ubb - engineStatus.nifty_ltp) > 0 ? 'text-green-600' : 'text-red-600'}">
													{(engineStatus.major_ubb - engineStatus.nifty_ltp).toFixed(2)}
												</span>
											{:else}
												<span class="text-gray-400">-</span>
											{/if}
										</td>
										<td class="px-4 py-3 text-sm text-gray-700">
											{engineStatus.major_trend_changed_at ? formatTime(engineStatus.major_trend_changed_at) : '-'}
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
									on:click={() => tradingInfoTab = 'positions'}
									class="flex-1 px-4 py-3 text-sm font-medium transition-colors {tradingInfoTab === 'positions' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
								>
									Positions ({positions.length || activeTrades.length})
								</button>
								<button
									on:click={() => tradingInfoTab = 'open-orders'}
									class="flex-1 px-4 py-3 text-sm font-medium transition-colors relative {tradingInfoTab === 'open-orders' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
								>
									<span>Open ({orders.filter(o => 
										o.status === 'OPEN' || 
										o.status === 'TRIGGER PENDING' || 
										o.status === 'AMO REQ RECEIVED' ||
										o.status === 'PENDING' ||
										o.status === 'VALIDATION PENDING' ||
										o.status === 'PUT ORDER REQ RECEIVED'
									).length || activeTrades.length})</span>
									<button
										on:click|stopPropagation={openManualOrderModal}
										class="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-green-500 text-white hover:bg-green-600 transition-colors"
										title="Place Manual Order"
									>
										<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
										</svg>
									</button>
								</button>
								<button
									on:click={() => tradingInfoTab = 'closed-orders'}
									class="flex-1 px-4 py-3 text-sm font-medium transition-colors {tradingInfoTab === 'closed-orders' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
								>
									Executed ({orders.filter(o => o.status === 'COMPLETE' || o.status === 'CANCELLED' || o.status === 'REJECTED').length})
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
									{@const sortedInstruments = [...instruments].sort((a, b) => {
										const order = { 'CE': 1, 'INDEX': 2, 'PE': 3 };
										return (order[a.type] || 999) - (order[b.type] || 999);
									})}
									<table class="w-full">
										<thead class="bg-gray-50 sticky top-0">
											<tr>
												<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Type</th>
												<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Symbol</th>
												<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Strike</th>
												<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">LTP</th>
												<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Qty</th>
												<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Value</th>

												<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Triggers</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-gray-200">
											{#each sortedInstruments as instrument}
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
														{#if instrument.type === 'INDEX'}
															{instrument.symbol.length > 20 ? instrument.symbol.substring(0, 20) + '...' : instrument.symbol}
														{:else}
															{instrument.tradingsymbol.length > 20 ? instrument.tradingsymbol.substring(0, 20) + '...' : instrument.tradingsymbol}
														{/if}
													</td>
													<td class="px-3 py-2 text-xs text-right text-gray-700">
														{instrument.type === 'INDEX' ? (instrument.ltp ? formatLTP(instrument.ltp) : '-') : (instrument.strike ? instrument.strike : '-')}
													</td>
													<td class="px-3 py-2 text-xs text-right font-medium text-gray-900">
														{instrument.ltp ? formatLTP(instrument.ltp) : '-'}
													</td>
													<td class="px-3 py-2 text-xs text-right text-gray-700">
														{instrument.type === 'INDEX' ? '' : (instrument.expected_quantity || '-')}
													</td>
													<td class="px-3 py-2 text-xs text-right text-gray-700">
														{instrument.type === 'INDEX' ? '' : (instrument.position_value ? formatCurrency(instrument.position_value) : '-')}
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
							{:else if tradingInfoTab === 'positions'}
								<!-- Open Positions Tab -->
								{#if positions.length > 0}
									<!-- Show broker positions (off-market) -->
									<table class="w-full">
										<thead class="bg-gray-50 sticky top-0">
											<tr>
												<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Instrument</th>
												<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Exchange</th>
												<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Qty</th>
												<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Buy Price</th>
												<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">LTP</th>
												<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">P&L</th>
												<th class="px-3 py-2 text-center text-xs font-semibold text-gray-700">Actions</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-gray-200">
											{#each positions as position}
												<tr class="hover:bg-gray-50">
													<td class="px-3 py-2 text-xs font-medium text-gray-900">{position.instrument || position.tradingsymbol}</td>
													<td class="px-3 py-2 text-xs text-gray-700">{position.exchange}</td>
													<td class="px-3 py-2 text-xs text-right text-gray-700">{position.quantity}</td>
													<td class="px-3 py-2 text-xs text-right text-gray-700">{formatCurrency(position.buy_price)}</td>
													<td class="px-3 py-2 text-xs text-right font-medium text-gray-900">{formatCurrency(position.last_price)}</td>
													<td class="px-3 py-2 text-xs text-right font-bold {getPnLColor(position.pnl || 0)}">
														{formatCurrency(position.pnl || 0)}
													</td>
													<td class="px-3 py-2 text-center">
														<button
															on:click={() => closeBrokerPosition(position)}
															class="text-red-600 hover:text-red-800"
															title="Close Position"
														>
															<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
															</svg>
														</button>
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								{:else if activeTrades.length === 0}
									<div class="text-center py-8 text-gray-500 text-sm">
										No open positions
									</div>
								{:else}
									<!-- Show engine trades (during market hours) -->
									<table class="w-full">
										<thead class="bg-gray-50 sticky top-0">
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
													<td class="px-3 py-2 text-xs text-right text-gray-700">{formatLTP(trade.entry_price)}</td>
													<td class="px-3 py-2 text-xs text-right font-medium text-gray-900">{formatLTP(trade.current_price || trade.entry_price)}</td>
													<td class="px-3 py-2 text-xs text-right font-bold {getPnLColor(trade.unrealized_pnl || 0)}">
														{formatCurrency(trade.unrealized_pnl || 0)}
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								{/if}
							{:else if tradingInfoTab === 'open-orders'}
								<!-- Open Orders Tab -->
								{#if orders.length > 0}
									<!-- Show broker orders (off-market) - Filter to show only open/pending orders -->
									{@const openOrders = orders.filter(o => 
										o.status === 'OPEN' || 
										o.status === 'TRIGGER PENDING' || 
										o.status === 'AMO REQ RECEIVED' ||
										o.status === 'PENDING' ||
										o.status === 'VALIDATION PENDING' ||
										o.status === 'PUT ORDER REQ RECEIVED'
									)}
									{#if openOrders.length > 0}
										<table class="w-full">
											<thead class="bg-gray-50">
												<tr>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Time</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Instrument</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Type</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Qty</th>
													<th class="px-3 py-2 text-right text-xs font-semibold text-gray-700">Price</th>
													<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Status</th>
													<th class="px-3 py-2 text-center text-xs font-semibold text-gray-700">Actions</th>
												</tr>
											</thead>
											<tbody class="divide-y divide-gray-200">
												{#each openOrders as order}
													<tr class="hover:bg-gray-50">
														<td class="px-3 py-2 text-xs text-gray-700">{order.order_timestamp ? formatTime(order.order_timestamp) : '-'}</td>
														<td class="px-3 py-2 text-xs font-medium text-gray-900">{order.tradingsymbol}</td>
														<td class="px-3 py-2">
															<span class="px-1.5 py-0.5 text-xs font-semibold rounded {order.transaction_type === 'BUY' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">
																{order.transaction_type}
															</span>
														</td>
														<td class="px-3 py-2 text-xs text-right text-gray-700">{order.quantity}</td>
														<td class="px-3 py-2 text-xs text-right text-gray-700">{formatCurrency(order.price)}</td>
														<td class="px-3 py-2 text-xs text-gray-700">{order.status}</td>
														<td class="px-3 py-2 text-center">
															<div class="flex items-center justify-center gap-2">
																{#if order.status === 'OPEN'}
																	<button
																		on:click={() => openModifyOrderModal(order)}
																		class="text-blue-600 hover:text-blue-800"
																		title="Modify Order"
																	>
																		<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
																		</svg>
																	</button>
																	<button
																		on:click={() => cancelOrder(order.order_id)}
																		class="text-red-600 hover:text-red-800"
																		title="Cancel Order"
																	>
																		<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
																		</svg>
																	</button>
																{:else}
																	<span class="text-xs text-gray-400">-</span>
																{/if}
															</div>
														</td>
													</tr>
												{/each}
											</tbody>
										</table>
									{:else}
										<div class="text-center py-8 text-gray-500 text-sm">
											No open orders
										</div>
									{/if}
								{:else if activeTrades.length === 0}
									<div class="text-center py-8 text-gray-500 text-sm">
										No open orders
									</div>
								{:else}
									<!-- Show engine trades (during market hours) -->
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
													<td class="px-3 py-2 text-xs text-right text-gray-700">{formatLTP(trade.entry_price)}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								{/if}
							{:else if tradingInfoTab === 'closed-orders'}
								<!-- Closed Orders Tab - Show Executed Orders -->
								{@const executedOrders = orders.filter(o => o.status === 'COMPLETE' || o.status === 'CANCELLED' || o.status === 'REJECTED')}
								{#if executedOrders.length === 0}
									<div class="text-center py-8 text-gray-500 text-sm">
										No executed orders
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
												<th class="px-3 py-2 text-left text-xs font-semibold text-gray-700">Status</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-gray-200">
											{#each executedOrders as order}
												<tr class="hover:bg-gray-50">
													<td class="px-3 py-2 text-xs text-gray-700">{order.order_timestamp ? formatTime(order.order_timestamp) : '-'}</td>
													<td class="px-3 py-2 text-xs font-medium text-gray-900">{order.tradingsymbol}</td>
													<td class="px-3 py-2">
														<span class="px-1.5 py-0.5 text-xs font-semibold rounded {order.transaction_type === 'BUY' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">
															{order.transaction_type}
														</span>
													</td>
													<td class="px-3 py-2 text-xs text-right text-gray-700">{order.quantity}</td>
													<td class="px-3 py-2 text-xs text-right text-gray-700">{formatCurrency(order.price)}</td>
													<td class="px-3 py-2">
														<span class="px-1.5 py-0.5 text-xs font-semibold rounded {
															order.status === 'COMPLETE' ? 'bg-green-100 text-green-700' :
															order.status === 'CANCELLED' ? 'bg-gray-100 text-gray-700' :
															'bg-red-100 text-red-700'
														}">
															{order.status}
														</span>
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

			<!-- Nifty 50 Position -->
			<div class="bg-white rounded-lg shadow-md p-6">
				
				{#if engineStatus.nifty_ltp && (engineStatus.minor_ma7 || engineStatus.major_ma7)}
					<!-- Header -->
					<div class="mb-4">
						<div class="text-2xl font-bold">
							<span class="text-black">Nifty 50:</span>
							<span class="{engineStatus.nifty_change !== undefined ? (engineStatus.nifty_change > 0 ? 'text-green-600' : engineStatus.nifty_change < 0 ? 'text-red-600' : 'text-black') : 'text-black'} ml-2">
								{formatLTP(engineStatus.nifty_ltp)}
							</span>
							{#if engineStatus.nifty_change !== undefined}
								<span class="{engineStatus.nifty_change >= 0 ? 'text-green-600' : 'text-red-600'} ml-2 text-lg">
									{engineStatus.nifty_change >= 0 ? '▲' : '▼'} {Math.abs(engineStatus.nifty_change).toFixed(2)} ({engineStatus.nifty_change_pct >= 0 ? '+' : ''}{engineStatus.nifty_change_pct?.toFixed(2)}%)
								</span>
							{/if}
						</div>
					</div>

					<!-- Trend Indicators -->
					<div class="space-y-4">
						<!-- Minor Trend -->
						{#if engineStatus.minor_trend}
							<div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
								<div class="flex justify-between items-center mb-3">
									<div class="flex items-center gap-2">
										<span class="text-sm font-semibold text-gray-700">Minor ({engineStatus.minor_timeframe})</span>
										<span class="text-sm font-bold {engineStatus.minor_trend.toLowerCase().includes('up') ? 'text-green-600' : 'text-red-600'}">
											{engineStatus.minor_trend.toLowerCase().includes('up') ? '▲' : '▼'}
										</span>
									</div>
								</div>

								<!-- Position Progress Bar -->
								{#if engineStatus.minor_lbb && engineStatus.minor_ubb && engineStatus.minor_ma20}
									{@const minorRange = engineStatus.minor_ubb - engineStatus.minor_lbb}
									{@const ma7Position = engineStatus.minor_ma7 ? ((engineStatus.minor_ma7 - engineStatus.minor_lbb) / minorRange) * 100 : 50}
									{@const ltpPosition = ((engineStatus.nifty_ltp - engineStatus.minor_lbb) / minorRange) * 100}
									<div class="space-y-1">
										<!-- LTP value above bar -->
										<div class="relative w-full h-4">
											<div class="absolute text-xs font-bold text-black transform -translate-x-1/2" style="left: {Math.max(5, Math.min(95, ltpPosition))}%">
												{formatLTP(engineStatus.nifty_ltp)}
											</div>
										</div>
										<!-- Progress bar -->
										<div class="relative w-full bg-gray-300 rounded-full h-2">
											<!-- LBB marker (left edge) -->
											<div class="absolute top-0 bottom-0 w-1 bg-blue-600 rounded-l-full" style="left: 0%"></div>
											<!-- UBB marker (right edge) -->
											<div class="absolute top-0 bottom-0 w-1 bg-blue-600 rounded-r-full" style="right: 0%"></div>
											<!-- 20 MA marker (center) -->
											<div class="absolute top-0 bottom-0 w-0.5 bg-red-600 z-10" style="left: 50%"></div>
											<!-- 7 MA marker -->
											{#if engineStatus.minor_ma7}
												<div class="absolute top-0 bottom-0 w-0.5 bg-green-600 z-10" style="left: {Math.max(0, Math.min(100, ma7Position))}%"></div>
											{/if}
											<!-- LTP marker -->
											<div class="absolute top-0 bottom-0 w-0.5 bg-black z-20" style="left: {Math.max(0, Math.min(100, ltpPosition))}%"></div>
										</div>
										<!-- Indicator values below bar -->
										<div class="relative w-full text-xs">
											<!-- LBB value (left) -->
											<span class="absolute left-0 text-blue-600 font-medium">{formatLTP(engineStatus.minor_lbb)}</span>
											<!-- 20MA value (center) -->
											<span class="absolute left-1/2 transform -translate-x-1/2 text-red-600 font-medium">{formatLTP(engineStatus.minor_ma20)}</span>
											<!-- UBB value (right) -->
											<span class="absolute right-0 text-blue-600 font-medium">{formatLTP(engineStatus.minor_ubb)}</span>
										</div>
									</div>
								{/if}
							</div>
						{/if}

						<!-- Major Trend -->
						{#if engineStatus.major_trend}
							<div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
								<div class="flex justify-between items-center mb-3">
									<div class="flex items-center gap-2">
										<span class="text-sm font-semibold text-gray-700">Major ({engineStatus.major_timeframe})</span>
										<span class="text-sm font-bold {engineStatus.major_trend.toLowerCase().includes('up') ? 'text-green-600' : 'text-red-600'}">
											{engineStatus.major_trend.toLowerCase().includes('up') ? '▲' : '▼'}
										</span>
									</div>
								</div>

								<!-- Position Progress Bar -->
								{#if engineStatus.major_lbb && engineStatus.major_ubb && engineStatus.major_ma20}
									{@const majorRange = engineStatus.major_ubb - engineStatus.major_lbb}
									{@const ma7Position = engineStatus.major_ma7 ? ((engineStatus.major_ma7 - engineStatus.major_lbb) / majorRange) * 100 : 50}
									{@const ltpPosition = ((engineStatus.nifty_ltp - engineStatus.major_lbb) / majorRange) * 100}
									<div class="space-y-1">
										<!-- LTP value above bar -->
										<div class="relative w-full h-4">
											<div class="absolute text-xs font-bold text-black transform -translate-x-1/2" style="left: {Math.max(5, Math.min(95, ltpPosition))}%">
												{formatLTP(engineStatus.nifty_ltp)}
											</div>
										</div>
										<!-- Progress bar -->
										<div class="relative w-full bg-gray-300 rounded-full h-2">
											<!-- LBB marker (left edge) -->
											<div class="absolute top-0 bottom-0 w-1 bg-blue-600 rounded-l-full" style="left: 0%"></div>
											<!-- UBB marker (right edge) -->
											<div class="absolute top-0 bottom-0 w-1 bg-blue-600 rounded-r-full" style="right: 0%"></div>
											<!-- 20 MA marker (center) -->
											<div class="absolute top-0 bottom-0 w-0.5 bg-red-600 z-10" style="left: 50%"></div>
											<!-- 7 MA marker -->
											{#if engineStatus.major_ma7}
												<div class="absolute top-0 bottom-0 w-0.5 bg-green-600 z-10" style="left: {Math.max(0, Math.min(100, ma7Position))}%"></div>
											{/if}
											<!-- LTP marker -->
											<div class="absolute top-0 bottom-0 w-0.5 bg-black z-20" style="left: {Math.max(0, Math.min(100, ltpPosition))}%"></div>
										</div>
										<!-- Indicator values below bar -->
										<div class="relative w-full text-xs">
											<!-- LBB value (left) -->
											<span class="absolute left-0 text-blue-600 font-medium">{formatLTP(engineStatus.major_lbb)}</span>
											<!-- 20MA value (center) -->
											<span class="absolute left-1/2 transform -translate-x-1/2 text-red-600 font-medium">{formatLTP(engineStatus.major_ma20)}</span>
											<!-- UBB value (right) -->
											<span class="absolute right-0 text-blue-600 font-medium">{formatLTP(engineStatus.major_ubb)}</span>
										</div>
									</div>
								{/if}
							</div>
						{/if}
					</div>

					<!-- Key Metrics -->
					<div class="mt-4 grid grid-cols-2 gap-3">
						{#if engineStatus.minor_ma7}
							<div class="bg-blue-50 rounded-lg p-3 text-center border border-blue-200">
								<div class="text-xs text-blue-600 mb-1">7MA (Minor)</div>
								<div class="text-sm font-bold text-blue-900">{engineStatus.minor_ma7.toFixed(2)}</div>
							</div>
						{/if}
						{#if engineStatus.major_ma7}
							<div class="bg-blue-50 rounded-lg p-3 text-center border border-blue-200">
								<div class="text-xs text-blue-600 mb-1">7MA (Major)</div>
								<div class="text-sm font-bold text-blue-900">{engineStatus.major_ma7.toFixed(2)}</div>
							</div>
						{/if}
						{#if engineStatus.minor_ma20}
							<div class="bg-blue-50 rounded-lg p-3 text-center border border-blue-200">
								<div class="text-xs text-blue-600 mb-1">20MA (Minor)</div>
								<div class="text-sm font-bold text-blue-900">{engineStatus.minor_ma20.toFixed(2)}</div>
							</div>
						{/if}
						{#if engineStatus.major_ma20}
							<div class="bg-blue-50 rounded-lg p-3 text-center border border-blue-200">
								<div class="text-xs text-blue-600 mb-1">20MA (Major)</div>
								<div class="text-sm font-bold text-blue-900">{engineStatus.major_ma20.toFixed(2)}</div>
							</div>
						{/if}
					</div>
				{:else}
					<div class="text-center py-8 text-gray-500">
						<p class="text-sm">Nifty 50 data not available</p>
					</div>
				{/if}
			</div>
			
			<!-- Alerts Card (Beside Performance, Below Nifty 50) -->
			<div class="lg:col-span-2 bg-white rounded-lg shadow-md p-6">
				<h2 class="text-xl font-bold mb-4">Alert ({alerts.length})</h2>
				
				<!-- Alert Tabs -->
				<div class="border-b border-gray-200 mb-4">
					<div class="flex gap-1">
						<button
							on:click={() => alertTab = 'system'}
							class="px-4 py-2 text-sm font-medium transition-colors {alertTab === 'system' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
						>
							System ({alerts.filter(a => a.type === 'system' || !a.type).length})
						</button>
						<button
							on:click={() => alertTab = 'broker'}
							class="px-4 py-2 text-sm font-medium transition-colors {alertTab === 'broker' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}"
						>
							Broker ({alerts.filter(a => a.type === 'broker').length})
						</button>
					</div>
				</div>
				
				<!-- Alert Content -->
				{#if alertTab === 'system'}
					<!-- System Alerts -->
					{#if alerts.filter(a => a.type === 'system' || !a.type).length === 0}
						<div class="text-center py-8 text-gray-500 text-sm">
							No system alerts
						</div>
					{:else}
						<div class="space-y-2 max-h-64 overflow-y-auto">
							{#each alerts.filter(a => a.type === 'system' || !a.type).slice(0, 10) as alert}
								<div class="flex items-center gap-2 p-3 rounded-lg bg-gray-50">
									<div class="w-3 h-3 rounded-full {
										alert.severity === 'info' ? 'bg-blue-500' :
										alert.severity === 'warning' ? 'bg-yellow-500' :
										alert.severity === 'error' ? 'bg-red-500' :
										alert.severity === 'critical' ? 'bg-red-700' :
										'bg-gray-500'
									}"></div>
									<div class="flex-1">
										<div class="flex items-center justify-between">
											<span class="text-sm font-medium text-gray-900">{alert.message}</span>
											<span class="text-xs text-gray-600">{formatTime(alert.timestamp)}</span>
										</div>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				{:else if alertTab === 'broker'}
					<!-- Broker Alerts -->
					{#if alerts.filter(a => a.type === 'broker').length === 0}
						<div class="text-center py-8 text-gray-500 text-sm">
							No broker alerts
						</div>
					{:else}
						<div class="space-y-2 max-h-64 overflow-y-auto">
							{#each alerts.filter(a => a.type === 'broker').slice(0, 10) as alert}
								<div class="flex items-center gap-2 p-3 rounded-lg bg-gray-50">
									<div class="w-3 h-3 rounded-full {
										alert.severity === 'info' ? 'bg-blue-500' :
										alert.severity === 'warning' ? 'bg-yellow-500' :
										alert.severity === 'error' ? 'bg-red-500' :
										alert.severity === 'critical' ? 'bg-red-700' :
										'bg-gray-500'
									}"></div>
									<div class="flex-1">
										<div class="flex items-center justify-between">
											<span class="text-sm font-medium text-gray-900">{alert.message}</span>
											<span class="text-xs text-gray-600">{formatTime(alert.timestamp)}</span>
										</div>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				{/if}
			</div>
		</div>
		
		<!-- Performance Card (After Alerts) -->
		<div class="bg-white rounded-lg shadow-md p-6 w-fit">
			<h2 class="text-xl font-bold mb-4">Performance</h2>
			<div class="overflow-x-auto">
				<table class="border-collapse">
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
						<!-- Available Funds Row -->
						<tr class="border-b border-gray-200">
							<td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50">Avl Funds</td>
							<td colspan="3" class="px-4 py-3 text-right">
								<div class="text-xl font-bold text-blue-600">{formatCurrency(funds.available)}</div>
							</td>
						</tr>
						<!-- Allocated Funds Row -->
						<tr class="border-b border-gray-200">
							<td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50">Allocated</td>
							<td colspan="3" class="px-4 py-3 text-right">
								<div class="text-xl font-bold text-orange-600">{formatCurrency(funds.allocated)}</div>
							</td>
						</tr>
						<!-- Remaining Funds Row -->
						<tr class="border-b border-gray-200">
							<td class="px-4 py-3 font-semibold text-gray-900 bg-gray-50">Remaining</td>
							<td colspan="3" class="px-4 py-3 text-right">
								<div class="text-xl font-bold text-green-600">{formatCurrency(funds.remaining)}</div>
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
		
		<!-- NIFTY 50 Candlestick Charts Card -->
		<div class="col-span-full bg-white rounded-lg shadow-md p-6">
			<h2 class="text-xl font-bold mb-4">NIFTY 50 Charts</h2>
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
				<!-- Major Timeframe Chart (15 minutes) -->
				<CandlestickChart 
					timeframe="15minute"
					title="Major Timeframe"
					height={350}
					wsLtp={engineStatus.nifty_ltp}
				/>
				
				<!-- Minor Timeframe Chart (1 minute) -->
				<CandlestickChart 
					timeframe="minute"
					title="Minor Timeframe"
					height={350}
					wsLtp={engineStatus.nifty_ltp}
				/>
			</div>
			
			<!-- Chart Info -->
			<div class="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
				<p class="text-xs text-blue-800">
					<span class="font-semibold">💡 Chart Info:</span>
					During market hours, charts update automatically using live data from WebSocket. 
					During off-market hours, historical data is fetched from the database/API.
					Green line = 7 MA, Red line = 20 MA, Blue dashed lines = Bollinger Bands.
				</p>
			</div>
		</div>
	{/if}
	
	<!-- Trades Tab -->
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
											<td class="px-4 py-3 text-sm text-right text-gray-700">{formatLTP(trade.entry_price)}</td>
											<td class="px-4 py-3 text-sm text-right font-medium text-gray-900">{formatLTP(trade.current_price || trade.entry_price)}</td>
											<td class="px-4 py-3 text-sm text-right text-green-600">{formatLTP(trade.target_price)}</td>
											<td class="px-4 py-3 text-sm text-right text-red-600">{formatLTP(trade.stoploss_price)}</td>
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
											<td class="px-4 py-3 text-sm text-right text-gray-700">{formatLTP(trade.entry_price)}</td>
											<td class="px-4 py-3 text-sm text-right text-gray-700">{formatLTP(trade.exit_price)}</td>
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
											<td class="px-4 py-3 text-sm text-right font-bold {getPnLColor(trade.realized_pnl)}">
												{formatCurrency(trade.realized_pnl)}
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
										alert.severity === 'info' ? 'bg-blue-500' :
										alert.severity === 'warning' ? 'bg-yellow-500' :
										alert.severity === 'error' ? 'bg-red-500' :
										alert.severity === 'critical' ? 'bg-red-700' :
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
</div>

<!-- Modify Order Modal -->
{#if showModifyModal}
	<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
		<div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
			<div class="px-6 py-4 border-b border-gray-200">
				<h3 class="text-lg font-semibold text-gray-900">Modify Order</h3>
			</div>
			<div class="px-6 py-4">
				<div class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Order ID</label>
						<input 
							type="text" 
							value={modifyOrderId} 
							disabled 
							class="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600"
						/>
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">New Price</label>
						<input 
							type="number" 
							bind:value={modifyPrice}
							step="0.01"
							class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							placeholder="Enter new price"
						/>
					</div>
				</div>
			</div>
			<div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
				<button
					on:click={() => showModifyModal = false}
					class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
				>
					Cancel
				</button>
				<button
					on:click={modifyOrder}
					class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
				>
					Save Changes
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Manual Order Placement Modal -->
{#if showManualOrderModal}
	<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
		<div class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
			<div class="px-6 py-4 border-b border-gray-200 sticky top-0 bg-white">
				<h3 class="text-lg font-semibold text-gray-900">Place Manual Order</h3>
			</div>
			<div class="px-6 py-4">
				<div class="grid grid-cols-2 gap-4">
					<!-- Trading Symbol -->
					<div class="col-span-2">
						<label class="block text-sm font-medium text-gray-700 mb-1">Trading Symbol *</label>
						<input 
							type="text" 
							bind:value={manualOrder.tradingsymbol}
							placeholder="e.g., NIFTY2411118000CE"
							class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						/>
						<p class="text-xs text-gray-500 mt-1">Example: NIFTY2411118000CE for Nifty options</p>
					</div>
					
					<!-- Exchange -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Exchange *</label>
						<select 
							bind:value={manualOrder.exchange}
							class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="NFO">NFO (Futures & Options)</option>
							<option value="NSE">NSE (Cash)</option>
							<option value="BSE">BSE (Cash)</option>
							<option value="BFO">BFO (BSE F&O)</option>
							<option value="CDS">CDS (Currency)</option>
							<option value="MCX">MCX (Commodity)</option>
						</select>
					</div>
					
					<!-- Transaction Type -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Transaction Type *</label>
						<select 
							bind:value={manualOrder.transaction_type}
							class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="BUY">BUY</option>
							<option value="SELL">SELL</option>
						</select>
					</div>
					
					<!-- Quantity -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Quantity *</label>
						<input 
							type="number" 
							bind:value={manualOrder.quantity}
							min="1"
							step="1"
							class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						/>
						<p class="text-xs text-gray-500 mt-1">Nifty lot size: 25, Bank Nifty: 15</p>
					</div>
					
					<!-- Order Type -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Order Type *</label>
						<select 
							bind:value={manualOrder.order_type}
							class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="LIMIT">LIMIT</option>
							<option value="MARKET">MARKET</option>
							<option value="SL">SL (Stop Loss Limit)</option>
							<option value="SL-M">SL-M (Stop Loss Market)</option>
						</select>
					</div>
					
					<!-- Product -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Product *</label>
						<select 
							bind:value={manualOrder.product}
							class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="MIS">MIS (Intraday)</option>
							<option value="NRML">NRML (Normal)</option>
							<option value="CNC">CNC (Cash & Carry)</option>
						</select>
					</div>
					
					<!-- Validity -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Validity</label>
						<select 
							bind:value={manualOrder.validity}
							class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="DAY">DAY</option>
							<option value="IOC">IOC (Immediate or Cancel)</option>
						</select>
					</div>
					
					<!-- Price (for LIMIT orders) -->
					{#if manualOrder.order_type === 'LIMIT' || manualOrder.order_type === 'SL'}
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Price * {manualOrder.order_type === 'LIMIT' ? '(Limit Price)' : '(Limit Price after trigger)'}</label>
							<input 
								type="number" 
								bind:value={manualOrder.price}
								step="0.05"
								min="0"
								class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								placeholder="Enter price"
							/>
						</div>
					{/if}
					
					<!-- Trigger Price (for SL orders) -->
					{#if manualOrder.order_type === 'SL' || manualOrder.order_type === 'SL-M'}
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Trigger Price *</label>
							<input 
								type="number" 
								bind:value={manualOrder.trigger_price}
								step="0.05"
								min="0"
								class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								placeholder="Enter trigger price"
							/>
						</div>
					{/if}
				</div>
				
				<!-- Order Summary -->
				<div class="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
					<p class="text-sm font-medium text-blue-900 mb-2">Order Summary</p>
					<div class="text-xs text-blue-800 space-y-1">
						<p><span class="font-semibold">{manualOrder.transaction_type}</span> {manualOrder.quantity} qty of <span class="font-semibold">{manualOrder.tradingsymbol || '___'}</span></p>
						<p>Type: <span class="font-semibold">{manualOrder.order_type}</span> | Product: <span class="font-semibold">{manualOrder.product}</span> | Exchange: <span class="font-semibold">{manualOrder.exchange}</span></p>
						{#if manualOrder.order_type === 'LIMIT' || manualOrder.order_type === 'SL'}
							<p>Price: <span class="font-semibold">₹{manualOrder.price || '___'}</span></p>
						{/if}
						{#if manualOrder.order_type === 'SL' || manualOrder.order_type === 'SL-M'}
							<p>Trigger: <span class="font-semibold">₹{manualOrder.trigger_price || '___'}</span></p>
						{/if}
					</div>
				</div>
			</div>
			<div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3 sticky bottom-0 bg-white">
				<button
					on:click={() => showManualOrderModal = false}
					class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
				>
				Cancel
			</button>
			<button
				on:click={placeManualOrder}
				class="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700"
			>
				Place Order
			</button>
		</div>
	</div>
</div>
{/if}

<!-- Charts Tab - Full Screen Advanced Chart -->
{#if mainTab === 'charts'}
	<div class="chart-fullscreen-container">
		<AdvancedChart />
	</div>
{/if}

<style>
	.chart-fullscreen-container {
		position: relative;
		width: 100%;
		height: calc(100vh - 200px); /* Subtract header + tabs height */
		min-height: 600px;
		background: white;
	}
</style>