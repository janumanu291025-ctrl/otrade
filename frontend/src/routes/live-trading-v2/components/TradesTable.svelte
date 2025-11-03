<script>
	import { trades, loading } from '../stores.js';
	
	let statusFilter = 'ALL';
	let currentPage = 1;
	const itemsPerPage = 20;
	
	function formatCurrency(value) {
		return new Intl.NumberFormat('en-IN', {
			style: 'currency',
			currency: 'INR',
			minimumFractionDigits: 2
		}).format(value || 0);
	}
	
	function formatDateTime(dateString) {
		if (!dateString) return 'N/A';
		const date = new Date(dateString);
		return date.toLocaleString('en-IN', {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
	
	function getStatusColor(status) {
		const colors = {
			OPEN: 'bg-blue-100 text-blue-800',
			CLOSED: 'bg-green-100 text-green-800',
			TARGET_HIT: 'bg-emerald-100 text-emerald-800',
			STOP_LOSS: 'bg-red-100 text-red-800',
			MANUAL_CLOSE: 'bg-gray-100 text-gray-800',
			EXPIRED: 'bg-yellow-100 text-yellow-800',
			ERROR: 'bg-red-100 text-red-800'
		};
		return colors[status] || 'bg-gray-100 text-gray-800';
	}
	
	function getPnLColor(pnl) {
		return pnl >= 0 ? 'text-green-600' : 'text-red-600';
	}
	
	$: filteredTrades = statusFilter === 'ALL'
		? $trades
		: $trades.filter(t => t.status === statusFilter);
	
	$: paginatedTrades = filteredTrades.slice(
		(currentPage - 1) * itemsPerPage,
		currentPage * itemsPerPage
	);
	
	$: totalPages = Math.ceil(filteredTrades.length / itemsPerPage);
	
	function handlePageChange(page) {
		currentPage = page;
	}
	
	function handleFilterChange() {
		currentPage = 1; // Reset to first page when filter changes
	}
</script>

<div class="bg-white rounded-lg shadow">
	<div class="px-6 py-4 border-b border-gray-200">
		<div class="flex items-center justify-between">
			<h2 class="text-lg font-semibold text-gray-900">
				Trade History
				<span class="text-sm font-normal text-gray-500 ml-2">
					({filteredTrades.length})
				</span>
			</h2>
			<div class="flex items-center gap-2">
				<label for="status-filter" class="text-sm text-gray-600">Filter:</label>
				<select
					id="status-filter"
					bind:value={statusFilter}
					on:change={handleFilterChange}
					class="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
				>
					<option value="ALL">All Trades</option>
					<option value="OPEN">Open</option>
					<option value="CLOSED">Closed</option>
					<option value="TARGET_HIT">Target Hit</option>
					<option value="STOP_LOSS">Stop Loss</option>
					<option value="MANUAL_CLOSE">Manual Close</option>
					<option value="EXPIRED">Expired</option>
				</select>
			</div>
		</div>
	</div>
	
	<div class="overflow-x-auto">
		{#if $loading.trades}
			<div class="flex justify-center items-center h-64">
				<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
			</div>
		{:else if paginatedTrades.length === 0}
			<div class="flex flex-col items-center justify-center h-64 text-gray-500">
				<svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
				</svg>
				<p class="text-lg font-medium">No trades found</p>
				<p class="text-sm">
					{statusFilter === 'ALL' ? 'Trade history will appear here' : `No ${statusFilter} trades`}
				</p>
			</div>
		{:else}
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							ID
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Instrument
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Entry
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Exit
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Qty
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							P&L
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Status
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Time
						</th>
					</tr>
				</thead>
				<tbody class="bg-white divide-y divide-gray-200">
					{#each paginatedTrades as trade (trade.id)}
						<tr class="hover:bg-gray-50 transition-colors">
							<td class="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-500">
								#{trade.id}
							</td>
							<td class="px-6 py-4 whitespace-nowrap">
								<div class="text-sm font-medium text-gray-900">
									{trade.instrument}
								</div>
								<div class="text-xs text-gray-500">
									{trade.option_type} @ {trade.strike_price}
								</div>
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
								{formatCurrency(trade.entry_price)}
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
								{trade.exit_price ? formatCurrency(trade.exit_price) : '-'}
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
								{trade.quantity}
							</td>
							<td class="px-6 py-4 whitespace-nowrap">
								{#if trade.realized_pnl !== null && trade.realized_pnl !== undefined}
									<div class={`text-sm font-bold ${getPnLColor(trade.realized_pnl)}`}>
										{formatCurrency(trade.realized_pnl)}
									</div>
									<div class={`text-xs ${getPnLColor(trade.realized_pnl_pct)}`}>
										({(trade.realized_pnl_pct || 0).toFixed(2)}%)
									</div>
								{:else if trade.unrealized_pnl !== null && trade.unrealized_pnl !== undefined}
									<div class={`text-sm font-bold ${getPnLColor(trade.unrealized_pnl)}`}>
										{formatCurrency(trade.unrealized_pnl)}
									</div>
									<div class="text-xs text-gray-500">(Unrealized)</div>
								{:else}
									<span class="text-sm text-gray-400">-</span>
								{/if}
							</td>
							<td class="px-6 py-4 whitespace-nowrap">
								<span class={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(trade.status)}`}>
									{trade.status.replace(/_/g, ' ')}
								</span>
							</td>
							<td class="px-6 py-4 whitespace-nowrap">
								<div class="text-sm text-gray-900">
									{formatDateTime(trade.entry_time)}
								</div>
								{#if trade.exit_time}
									<div class="text-xs text-gray-500">
										→ {formatDateTime(trade.exit_time)}
									</div>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
			
			{#if totalPages > 1}
				<div class="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
					<div class="text-sm text-gray-500">
						Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, filteredTrades.length)} of {filteredTrades.length} trades
					</div>
					<div class="flex gap-2">
						<button
							on:click={() => handlePageChange(currentPage - 1)}
							disabled={currentPage === 1}
							class="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
						>
							Previous
						</button>
						{#each Array.from({ length: totalPages }, (_, i) => i + 1) as page}
							{#if page === 1 || page === totalPages || (page >= currentPage - 1 && page <= currentPage + 1)}
								<button
									on:click={() => handlePageChange(page)}
									class={`px-3 py-1 text-sm border rounded-md ${
										page === currentPage
											? 'bg-blue-600 text-white border-blue-600'
											: 'border-gray-300 hover:bg-gray-50'
									}`}
								>
									{page}
								</button>
							{:else if page === currentPage - 2 || page === currentPage + 2}
								<span class="px-2 py-1 text-sm text-gray-400">...</span>
							{/if}
						{/each}
						<button
							on:click={() => handlePageChange(currentPage + 1)}
							disabled={currentPage === totalPages}
							class="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
						>
							Next
						</button>
					</div>
				</div>
			{/if}
		{/if}
	</div>
</div>
