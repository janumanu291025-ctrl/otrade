<script>
	import { funds, fundsUtilizationColor } from '../stores.js';
	
	function formatCurrency(value) {
		return new Intl.NumberFormat('en-IN', {
			style: 'currency',
			currency: 'INR',
			minimumFractionDigits: 2
		}).format(value || 0);
	}
	
	$: utilizationWidth = `${Math.min($funds.utilization_pct || 0, 100)}%`;
</script>

<div class="bg-white rounded-lg shadow p-6">
	<h2 class="text-lg font-semibold text-gray-900 mb-4">Funds Status</h2>
	
	<div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
		<!-- Available Funds -->
		<div>
			<div class="text-sm font-medium text-gray-500 mb-1">Available</div>
			<div class="text-2xl font-bold text-gray-900">
				{formatCurrency($funds.available)}
			</div>
		</div>
		
		<!-- Allocated Funds -->
		<div>
			<div class="text-sm font-medium text-gray-500 mb-1">Allocated</div>
			<div class="text-2xl font-bold text-blue-600">
				{formatCurrency($funds.allocated)}
			</div>
		</div>
		
		<!-- Remaining Funds -->
		<div>
			<div class="text-sm font-medium text-gray-500 mb-1">Remaining</div>
			<div class="text-2xl font-bold text-green-600">
				{formatCurrency($funds.remaining)}
			</div>
		</div>
		
		<!-- Utilization -->
		<div>
			<div class="text-sm font-medium text-gray-500 mb-1">Utilization</div>
			<div class={`text-2xl font-bold ${$fundsUtilizationColor}`}>
				{($funds.utilization_pct || 0).toFixed(1)}%
			</div>
		</div>
	</div>
	
	<!-- Utilization Bar -->
	<div class="relative">
		<div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
			<div
				class="h-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500 transition-all duration-500"
				style="width: {utilizationWidth}"
			></div>
		</div>
		
		<!-- Markers -->
		<div class="flex justify-between text-xs text-gray-500 mt-1">
			<span>0%</span>
			<span>50%</span>
			<span>100%</span>
		</div>
	</div>
</div>
