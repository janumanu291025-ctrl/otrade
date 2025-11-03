<script>
	import { createEventDispatcher } from 'svelte';
	import { positions, loading } from '../stores.js';
	
	const dispatch = createEventDispatcher();
	
	function formatCurrency(value) {
		return new Intl.NumberFormat('en-IN', {
			style: 'currency',
			currency: 'INR',
			minimumFractionDigits: 2
		}).format(value || 0);
	}
	
	function formatTime(dateString) {
		if (!dateString) return 'N/A';
		const date = new Date(dateString);
		return date.toLocaleTimeString('en-IN', {
			hour: '2-digit',
			minute: '2-digit'
		});
	}
	
	function handleClose(tradeId) {
		dispatch('closePosition', { tradeId });
	}
	
	function getPnLColor(pnl) {
		return pnl >= 0 ? 'text-green-600' : 'text-red-600';
	}
	
	function getTargetProgress(position) {
		if (!position.current_price || !position.entry_price || !position.target_price) {
			return 0;
		}
		const totalMove = position.target_price - position.entry_price;
		const currentMove = position.current_price - position.entry_price;
		return Math.min(Math.max((currentMove / totalMove) * 100, 0), 100);
	}
</script>

<div class="bg-white rounded-lg shadow">
	<div class="px-6 py-4 border-b border-gray-200">
		<h2 class="text-lg font-semibold text-gray-900">
			Open Positions
			<span class="text-sm font-normal text-gray-500 ml-2">
				({$positions.length})
			</span>
		</h2>
	</div>
	
	<div class="overflow-x-auto">
		{#if $loading.positions}
			<div class="flex justify-center items-center h-64">
				<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
			</div>
		{:else if $positions.length === 0}
			<div class="flex flex-col items-center justify-center h-64 text-gray-500">
				<svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
				</svg>
				<p class="text-lg font-medium">No open positions</p>
				<p class="text-sm">Positions will appear here when trades are executed</p>
			</div>
		{:else}
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Instrument
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Entry
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Current
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Target / SL
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Qty
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							P&L
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Progress
						</th>
						<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
							Action
						</th>
					</tr>
				</thead>
				<tbody class="bg-white divide-y divide-gray-200">
					{#each $positions as position (position.id)}
						<tr class="hover:bg-gray-50 transition-colors">
							<td class="px-6 py-4 whitespace-nowrap">
								<div class="text-sm font-medium text-gray-900">
									{position.instrument}
								</div>
								<div class="text-xs text-gray-500">
									{position.option_type} @ {position.strike_price}
								</div>
								<div class="text-xs text-gray-400">
									{formatTime(position.entry_time)}
								</div>
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
								{formatCurrency(position.entry_price)}
							</td>
							<td class="px-6 py-4 whitespace-nowrap">
								<div class="text-sm font-medium text-gray-900">
									{formatCurrency(position.current_price)}
								</div>
								{#if position.ltp_available}
									<div class="flex items-center gap-1 text-xs text-green-600">
										<div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
										Live
									</div>
								{/if}
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm">
								<div class="text-green-600">
									T: {formatCurrency(position.target_price)}
								</div>
								<div class="text-red-600">
									SL: {formatCurrency(position.stoploss_price)}
								</div>
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
								{position.quantity}
							</td>
							<td class="px-6 py-4 whitespace-nowrap">
								<div class={`text-sm font-bold ${getPnLColor(position.unrealized_pnl)}`}>
									{formatCurrency(position.unrealized_pnl)}
								</div>
								<div class={`text-xs ${getPnLColor(position.unrealized_pnl_pct)}`}>
									({(position.unrealized_pnl_pct || 0).toFixed(2)}%)
								</div>
							</td>
							<td class="px-6 py-4 whitespace-nowrap">
								<div class="w-24">
									<div class="relative pt-1">
										<div class="overflow-hidden h-2 text-xs flex rounded bg-gray-200">
											<div
												style="width: {getTargetProgress(position)}%"
												class={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center ${
													getTargetProgress(position) >= 100
														? 'bg-green-500'
														: getTargetProgress(position) >= 75
															? 'bg-yellow-500'
															: 'bg-blue-500'
												}`}
											></div>
										</div>
									</div>
									<div class="text-xs text-center text-gray-500 mt-1">
										{getTargetProgress(position).toFixed(0)}%
									</div>
								</div>
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-right text-sm">
								<button
									on:click={() => handleClose(position.id)}
									class="text-red-600 hover:text-red-900 font-medium"
								>
									Close
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</div>
</div>
