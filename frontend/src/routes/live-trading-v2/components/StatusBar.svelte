<script>
	import { engineStatus, pnl } from '../stores.js';
	
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
			dateStyle: 'short',
			timeStyle: 'short'
		});
	}
	
	$: statusColor = $engineStatus.running
		? ($engineStatus.paused ? 'yellow' : 'green')
		: 'gray';
	
	$: statusText = $engineStatus.running
		? ($engineStatus.paused ? 'PAUSED' : 'RUNNING')
		: 'STOPPED';
	
	$: pnlColor = $pnl.total >= 0 ? 'text-green-600' : 'text-red-600';
</script>

<div class="bg-white rounded-lg shadow p-6">
	<div class="grid grid-cols-1 md:grid-cols-4 gap-6">
		<!-- Status -->
		<div>
			<div class="text-sm font-medium text-gray-500 mb-1">Status</div>
			<div class="flex items-center gap-2">
				<div class={`w-3 h-3 rounded-full bg-${statusColor}-500`}></div>
				<span class={`text-lg font-bold text-${statusColor}-700`}>
					{statusText}
				</span>
			</div>
			{#if $engineStatus.config_name}
				<div class="text-xs text-gray-600 mt-1">
					{$engineStatus.config_name}
				</div>
			{/if}
		</div>
		
		<!-- Contract Expiry -->
		<div>
			<div class="text-sm font-medium text-gray-500 mb-1">Contract Expiry</div>
			<div class="text-lg font-semibold text-gray-900">
				{$engineStatus.contract_expiry || 'Auto'}
			</div>
		</div>
		
		<!-- Started At -->
		<div>
			<div class="text-sm font-medium text-gray-500 mb-1">Started At</div>
			<div class="text-sm font-medium text-gray-900">
				{formatDateTime($engineStatus.started_at)}
			</div>
		</div>
		
		<!-- Total P&L -->
		<div>
			<div class="text-sm font-medium text-gray-500 mb-1">Total P&L</div>
			<div class={`text-2xl font-bold ${pnlColor}`}>
				{formatCurrency($pnl.total)}
			</div>
			<div class="flex gap-2 text-xs mt-1">
				<span class="text-green-600">
					R: {formatCurrency($pnl.realized)}
				</span>
				<span class="text-gray-600">|</span>
				<span class="text-blue-600">
					U: {formatCurrency($pnl.unrealized)}
				</span>
			</div>
		</div>
	</div>
</div>
