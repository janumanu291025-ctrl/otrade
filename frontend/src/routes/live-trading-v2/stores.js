/**
 * Live Trading V2 Stores
 * Svelte stores for managing live trading state with performance optimizations
 */
import { writable, derived } from 'svelte/store';

/**
 * Debounce function to limit update frequency
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
	let timeout;
	return function executedFunction(...args) {
		const later = () => {
			clearTimeout(timeout);
			func(...args);
		};
		clearTimeout(timeout);
		timeout = setTimeout(later, wait);
	};
}

/**
 * Create a debounced writable store
 * @param {any} initial - Initial value
 * @param {number} debounceMs - Debounce time in milliseconds
 * @returns {Object} Writable store with debounced updates
 */
function debouncedWritable(initial, debounceMs = 100) {
	const store = writable(initial);
	const debouncedSet = debounce((value) => store.set(value), debounceMs);
	
	return {
		subscribe: store.subscribe,
		set: debouncedSet,
		update: (fn) => {
			store.update((value) => {
				const newValue = fn(value);
				debouncedSet(newValue);
				return value; // Return original to prevent immediate update
			});
		},
		setImmediate: store.set // Allow immediate updates when needed
	};
}

// Engine status store (no debounce - immediate updates needed)
export const engineStatus = writable({
	running: false,
	paused: false,
	config_id: null,
	config_name: null,
	contract_expiry: null,
	started_at: null
});

// Funds store (no debounce - immediate updates)
export const funds = writable({
	available: 0,
	allocated: 0,
	remaining: 0,
	utilization_pct: 0
});

// Positions store (debounced - can update frequently from WebSocket)
export const positions = debouncedWritable([], 200);

// Trades store (debounced - less critical for real-time)
export const trades = debouncedWritable([], 300);

// Alerts store (no debounce - immediate visibility needed)
export const alerts = writable([]);

// Signals store (debounced)
export const signals = debouncedWritable([], 200);

// P&L store
export const pnl = writable({
	realized: 0,
	unrealized: 0,
	total: 0
});

// Trading configs store
export const configs = writable([]);

// Token expiry modal store
export const showTokenExpiredModal = writable(false);

// WebSocket connection status
export const wsConnected = writable(false);

// Loading states
export const loading = writable({
	status: false,
	positions: false,
	trades: false,
	alerts: false
});

// Derived stores
export const positionCount = derived(
	positions,
	$positions => $positions.length
);

export const totalUnrealizedPnL = derived(
	positions,
	$positions => $positions.reduce((sum, pos) => sum + (pos.unrealized_pnl || 0), 0)
);

export const fundsUtilizationColor = derived(
	funds,
	$funds => {
		const util = $funds.utilization_pct || 0;
		if (util < 50) return 'text-green-600';
		if (util < 75) return 'text-yellow-600';
		return 'text-red-600';
	}
);

// Helper functions
export function resetStores() {
	engineStatus.set({
		running: false,
		paused: false,
		config_id: null,
		config_name: null,
		contract_expiry: null,
		started_at: null
	});
	funds.set({ available: 0, allocated: 0, remaining: 0, utilization_pct: 0 });
	positions.set([]);
	trades.set([]);
	alerts.set([]);
	signals.set([]);
	pnl.set({ realized: 0, unrealized: 0, total: 0 });
}
