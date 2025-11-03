<script>
	import { alerts, loading } from '../stores.js';
	
	let severityFilter = 'ALL';
	
	function getSeverityColor(severity) {
		const colors = {
			CRITICAL: 'bg-red-50 border-red-200 text-red-800',
			ERROR: 'bg-red-50 border-red-200 text-red-700',
			WARNING: 'bg-yellow-50 border-yellow-200 text-yellow-800',
			INFO: 'bg-blue-50 border-blue-200 text-blue-800',
			SUCCESS: 'bg-green-50 border-green-200 text-green-800'
		};
		return colors[severity] || 'bg-gray-50 border-gray-200 text-gray-800';
	}
	
	function getSeverityIcon(severity) {
		switch (severity) {
			case 'CRITICAL':
			case 'ERROR':
				return '⛔';
			case 'WARNING':
				return '⚠️';
			case 'INFO':
				return 'ℹ️';
			case 'SUCCESS':
				return '✅';
			default:
				return '•';
		}
	}
	
	function formatTime(dateString) {
		if (!dateString) return 'N/A';
		const date = new Date(dateString);
		const now = new Date();
		const diffMs = now - date;
		const diffMins = Math.floor(diffMs / 60000);
		
		if (diffMins < 1) return 'Just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		
		const diffHours = Math.floor(diffMins / 60);
		if (diffHours < 24) return `${diffHours}h ago`;
		
		return date.toLocaleString('en-IN', {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
	
	$: filteredAlerts = severityFilter === 'ALL'
		? $alerts
		: $alerts.filter(a => a.severity === severityFilter);
	
	$: sortedAlerts = [...filteredAlerts].sort((a, b) => {
		return new Date(b.timestamp) - new Date(a.timestamp);
	});
</script>

<div class="bg-white rounded-lg shadow">
	<div class="px-6 py-4 border-b border-gray-200">
		<div class="flex items-center justify-between">
			<h2 class="text-lg font-semibold text-gray-900">
				Alerts
				<span class="text-sm font-normal text-gray-500 ml-2">
					({filteredAlerts.length})
				</span>
			</h2>
			<div class="flex items-center gap-2">
				<label for="severity-filter" class="text-sm text-gray-600">Filter:</label>
				<select
					id="severity-filter"
					bind:value={severityFilter}
					class="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
				>
					<option value="ALL">All</option>
					<option value="CRITICAL">Critical</option>
					<option value="ERROR">Error</option>
					<option value="WARNING">Warning</option>
					<option value="INFO">Info</option>
					<option value="SUCCESS">Success</option>
				</select>
			</div>
		</div>
	</div>
	
	<div class="max-h-96 overflow-y-auto">
		{#if $loading.alerts}
			<div class="flex justify-center items-center h-64">
				<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
			</div>
		{:else if sortedAlerts.length === 0}
			<div class="flex flex-col items-center justify-center h-64 text-gray-500">
				<svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
				</svg>
				<p class="text-lg font-medium">No alerts</p>
				<p class="text-sm">
					{severityFilter === 'ALL' ? 'Alerts will appear here' : `No ${severityFilter} alerts`}
				</p>
			</div>
		{:else}
			<div class="divide-y divide-gray-200">
				{#each sortedAlerts as alert (alert.id)}
					<div class={`p-4 border-l-4 ${getSeverityColor(alert.severity)}`}>
						<div class="flex items-start gap-3">
							<div class="text-2xl mt-0.5">
								{getSeverityIcon(alert.severity)}
							</div>
							<div class="flex-1 min-w-0">
								<div class="flex items-center justify-between gap-2">
									<div class="flex items-center gap-2">
										<span class="text-xs font-semibold uppercase tracking-wide">
											{alert.severity}
										</span>
										{#if alert.instrument}
											<span class="text-xs text-gray-500">
												• {alert.instrument}
											</span>
										{/if}
									</div>
									<span class="text-xs text-gray-500 whitespace-nowrap">
										{formatTime(alert.timestamp)}
									</span>
								</div>
								<p class="mt-1 text-sm font-medium">
									{alert.message}
								</p>
								{#if alert.details}
									<p class="mt-1 text-xs text-gray-600">
										{alert.details}
									</p>
								{/if}
								{#if alert.trade_id}
									<div class="mt-2 text-xs text-gray-500">
										Trade #{alert.trade_id}
									</div>
								{/if}
							</div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
	
	{#if sortedAlerts.length > 0}
		<div class="px-6 py-3 border-t border-gray-200 bg-gray-50">
			<div class="flex items-center justify-between text-xs text-gray-500">
				<span>
					Showing most recent alerts
				</span>
				{#if $alerts.filter(a => a.severity === 'CRITICAL' || a.severity === 'ERROR').length > 0}
					<span class="text-red-600 font-medium">
						{$alerts.filter(a => a.severity === 'CRITICAL' || a.severity === 'ERROR').length} critical/error alerts
					</span>
				{/if}
			</div>
		</div>
	{/if}
</div>
