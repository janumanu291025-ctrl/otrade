<script>
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';

	let chartContainer;
	let chart;
	let candlestickSeries;
	let ma7Series;
	let ma20Series;
	let bbUpperSeries;
	let bbLowerSeries;
	let rocSeries;
	let rocZeroLineSeries;
	let rocChart;
	let rocChartContainer;
	
	let timeframe = '15minute';
	let isLoading = false;
	let error = null;
	let rocPeriod = 9;
	let rocPeriodInput = 9;

	const timeframes = [
		{ value: 'minute', label: '1 Minute' },
		{ value: '3minute', label: '3 Minutes' },
		{ value: '5minute', label: '5 Minutes' },
		{ value: '15minute', label: '15 Minutes' },
		{ value: '30minute', label: '30 Minutes' },
		{ value: '60minute', label: '1 Hour' },
		{ value: 'day', label: 'Daily' }
	];

	function calculateROC(closes, period) {
		const roc = [];
		for (let i = 0; i < closes.length; i++) {
			if (i < period) {
				roc.push(null);
			} else {
				const change = ((closes[i] - closes[i - period]) / closes[i - period]) * 100;
				roc.push(change);
			}
		}
		return roc;
	}

	async function fetchChartData() {
		if (!browser) return;
		
		try {
			isLoading = true;
			error = null;
			
			const response = await fetch(
				`http://localhost:8000/api/live-trading-v2/chart-data?timeframe=${timeframe}&limit=5000`
			);
			
			if (!response.ok) {
				throw new Error(`Failed to fetch chart data: ${response.statusText}`);
			}
			
			const data = await response.json();
			updateChart(data);
		} catch (err) {
			console.error('Error fetching chart data:', err);
			error = err.message;
		} finally {
			isLoading = false;
		}
	}

	function updateROCPeriod() {
		rocPeriod = rocPeriodInput;
		// Recalculate ROC and update chart if data exists
		const allCandles = candlestickSeries?.data();
		if (allCandles && allCandles.length > 0) {
			const closes = allCandles.map(c => c.close);
			const rocValues = calculateROC(closes, rocPeriod);
			
			const rocData = rocValues.map((value, index) => ({
				time: allCandles[index].time,
				value: value
			})).filter(d => d.value !== null);
			
			if (rocSeries && rocData.length > 0) {
				rocSeries.setData(rocData);
			}

			// Update zero line
			if (rocZeroLineSeries && allCandles.length > 0) {
				const zeroLineData = allCandles.map(c => ({
					time: c.time,
					value: 0
				}));
				rocZeroLineSeries.setData(zeroLineData);
			}
		}
	}

	function updateChart(data) {
		if (!data || !data.candles || data.candles.length === 0) {
			error = 'No data available';
			return;
		}

		// Format candles
		const candles = data.candles.map(c => ({
			time: c.timestamp / 1000,
			open: c.open,
			high: c.high,
			low: c.low,
			close: c.close
		}));

		// Update candlestick series
		if (candlestickSeries) {
			candlestickSeries.setData(candles);
		}

		// Update MA7
		if (ma7Series && data.ma7 && data.ma7.length > 0) {
			const ma7Data = data.ma7.map(m => ({
				time: m.timestamp / 1000,
				value: m.value
			}));
			ma7Series.setData(ma7Data);
		}

		// Update MA20
		if (ma20Series && data.ma20 && data.ma20.length > 0) {
			const ma20Data = data.ma20.map(m => ({
				time: m.timestamp / 1000,
				value: m.value
			}));
			ma20Series.setData(ma20Data);
		}

		// Update Bollinger Bands Upper
		if (bbUpperSeries && data.bb_upper && data.bb_upper.length > 0) {
			const bbUpperData = data.bb_upper.map(b => ({
				time: b.timestamp / 1000,
				value: b.value
			}));
			bbUpperSeries.setData(bbUpperData);
		}

		// Update Bollinger Bands Lower
		if (bbLowerSeries && data.bb_lower && data.bb_lower.length > 0) {
			const bbLowerData = data.bb_lower.map(b => ({
				time: b.timestamp / 1000,
				value: b.value
			}));
			bbLowerSeries.setData(bbLowerData);
		}

		// Calculate and update ROC
		if (rocSeries && candlestickSeries) {
			const allCandles = candlestickSeries.data();
			if (allCandles && allCandles.length > rocPeriod) {
				const closes = allCandles.map(c => c.close);
				const rocValues = calculateROC(closes, rocPeriod);
				
				const rocData = rocValues.map((value, index) => ({
					time: allCandles[index].time,
					value: value
				})).filter(d => d.value !== null);
				
				if (rocData.length > 0) {
					rocSeries.setData(rocData);
				}

				// Set zero line data
				if (rocZeroLineSeries) {
					const zeroLineData = allCandles.map(c => ({
						time: c.time,
						value: 0
					}));
					rocZeroLineSeries.setData(zeroLineData);
				}
			}
		}

		// Fit content
		if (chart) {
			chart.timeScale().fitContent();
		}
		if (rocChart) {
			rocChart.timeScale().fitContent();
		}
	}

	async function initChart() {
		if (!browser || !chartContainer) return;

		try {
			// Import v5 API - correct format
			const { createChart, CandlestickSeries, LineSeries } = await import('lightweight-charts');

			// Create the chart
			chart = createChart(chartContainer, {
				width: chartContainer.clientWidth,
				height: 750,
				layout: {
					background: { color: '#ffffff' },
					textColor: '#333',
					fontSize: 12,
					fontFamily: 'Trebuchet MS, Roboto, Ubuntu, sans-serif'
				},
				grid: {
					vertLines: { color: '#f5f5f5', style: 0 },
					horzLines: { color: '#f5f5f5', style: 0 }
				},
				timeScale: {
					timeVisible: true,
					secondsVisible: false,
					borderVisible: false,
					borderColor: '#ffffff'
				},
				rightPriceScale: {
					borderVisible: false,
					borderColor: '#ffffff',
					textColor: '#333',
					visible: true,
					mode: 0,
					autoScale: true,
					entireTextOnly: false,
					minWidth: 60
				},
				crosshair: {
					mode: 1,
					vertLine: {
						width: 1,
						color: '#9598A1',
						style: 1  // Dotted style
					},
					horzLine: {
						width: 1,
						color: '#9598A1',
						style: 1  // Dotted style
					}
				},
				handleScroll: {
					mouseWheel: true,
					pressedMouseMove: true
				},
				handleScale: {
					axisPressedMouseMove: true,
					mouseWheel: true,
					pinch: true
				},
				watermark: {
					visible: false
				}
			});

			// Create series using v5 API: chart.addSeries(SeriesType, options)
			candlestickSeries = chart.addSeries(CandlestickSeries, {
				upColor: '#26a69a',
				downColor: '#ef5350',
				borderVisible: false,
				wickUpColor: '#26a69a',
				wickDownColor: '#ef5350'
			});

			// Create MA7 series (indigo line)
			ma7Series = chart.addSeries(LineSeries, {
				color: '#4B0082',
				lineWidth: 1,
				priceLineVisible: false,
				lastValueVisible: false,
				priceScaleId: 'right',
				crosshairMarkerVisible: false
			});

			// Create MA20 series (blood red line)
			ma20Series = chart.addSeries(LineSeries, {
				color: '#DC143C',
				lineWidth: 1,
				priceLineVisible: false,
				lastValueVisible: false,
				priceScaleId: 'right',
				crosshairMarkerVisible: false
			});

			// Create Bollinger Bands Upper (blue dashed)
			bbUpperSeries = chart.addSeries(LineSeries, {
				color: '#2196F3',
				lineWidth: 0.5,
				lineStyle: 2, // Dashed
				priceLineVisible: false,
				lastValueVisible: false,
				priceScaleId: 'right',
				crosshairMarkerVisible: false
			});

			// Create Bollinger Bands Lower (blue dashed)
			bbLowerSeries = chart.addSeries(LineSeries, {
				color: '#2196F3',
				lineWidth: 0.5,
				lineStyle: 2, // Dashed
				priceLineVisible: false,
				lastValueVisible: false,
				priceScaleId: 'right',
				crosshairMarkerVisible: false
			});

			// Create separate ROC chart at the bottom
			if (rocChartContainer) {
				rocChart = createChart(rocChartContainer, {
					width: rocChartContainer.clientWidth,
					height: 200,
					layout: {
						background: { color: '#FFFFF0' },
						textColor: '#333',
						fontSize: 12,
						fontFamily: 'Trebuchet MS, Roboto, Ubuntu, sans-serif'
					},
					grid: {
						vertLines: { color: 'transparent', style: 0 },
						horzLines: { color: 'transparent', style: 0 }
					},
					timeScale: {
						timeVisible: true,
						secondsVisible: false,
						borderVisible: false,
						borderColor: '#ffffff'
					},
					rightPriceScale: {
						borderVisible: false,
						borderColor: '#ffffff',
						textColor: '#333',
						visible: true
					},
					crosshair: {
						mode: 1,
						vertLine: {
							width: 1,
							color: '#9598A1',
							style: 1
						},
						horzLine: {
							width: 1,
							color: '#9598A1',
							style: 1
						}
					},
					handleScroll: {
						mouseWheel: true,
						pressedMouseMove: true
					},
					handleScale: {
						axisPressedMouseMove: true,
						mouseWheel: true,
						pinch: true
					},
					watermark: {
						visible: false
					}
				});

				rocSeries = rocChart.addSeries(LineSeries, {
					color: '#FF8C00',
					lineWidth: 1,
					priceLineVisible: false,
					lastValueVisible: false,
					crosshairMarkerVisible: false
				});

				// Add zero line (blood red dotted)
				rocZeroLineSeries = rocChart.addSeries(LineSeries, {
					color: '#DC143C',
					lineWidth: 1,
					priceLineVisible: false,
					lastValueVisible: false,
					crosshairMarkerVisible: false,
					lineStyle: 2  // Dotted line
				});

				// Sync time scales between main chart and ROC chart
				chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
					rocChart.timeScale().setVisibleLogicalRange(range);
				});

				rocChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
					chart.timeScale().setVisibleLogicalRange(range);
				});

				// Handle resize for ROC chart
				const rocResizeObserver = new ResizeObserver(() => {
					if (rocChart && rocChartContainer) {
						rocChart.applyOptions({
							width: rocChartContainer.clientWidth
						});
					}
				});
				rocResizeObserver.observe(rocChartContainer);
			}

			// Handle resize for main chart
			const resizeObserver = new ResizeObserver(() => {
				if (chart && chartContainer) {
					chart.applyOptions({
						width: chartContainer.clientWidth
					});
				}
			});
			resizeObserver.observe(chartContainer);

			// Fetch initial data
			await fetchChartData();
		} catch (err) {
			console.error('Error initializing chart:', err);
			error = 'Failed to initialize chart';
		}
	}

	async function handleTimeframeChange() {
		await fetchChartData();
	}

	onMount(async () => {
		await initChart();
	});

	onDestroy(() => {
		if (chart) {
			chart.remove();
		}
		if (rocChart) {
			rocChart.remove();
		}
	});
</script>

<div class="container mx-auto p-6">
	<div class="bg-white rounded-lg shadow-lg p-6">
		<!-- Header -->
		<div class="flex items-center justify-between mb-6">
			<h1 class="text-2xl font-bold text-gray-800">Nifty 50</h1>
			
			<!-- Timeframe Selector -->
			<div class="flex items-center gap-4">
				<label for="rocPeriod" class="text-sm font-medium text-gray-700">ROC</label>
				<input
					id="rocPeriod"
					type="number"
					min="1"
					max="100"
					bind:value={rocPeriodInput}
					on:change={updateROCPeriod}
					class="px-3 py-2 w-16 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
				/>
				
				<label for="timeframe" class="text-sm font-medium text-gray-700"></label>
				<select
					id="timeframe"
					bind:value={timeframe}
					on:change={handleTimeframeChange}
					class="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
				>
					{#each timeframes as tf}
						<option value={tf.value}>{tf.label}</option>
					{/each}
				</select>
			</div>
		</div>

		<!-- Error Message -->
		{#if error}
			<div class="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
				<p class="text-red-800 text-sm">⚠️ {error}</p>
			</div>
		{/if}

		<!-- Loading Indicator -->
		{#if isLoading}
			<div class="mb-4 flex items-center justify-center">
				<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
				<span class="ml-3 text-gray-600">Loading chart data...</span>
			</div>
		{/if}

		<!-- Chart Container -->
		<div class="overflow-hidden" style="height: 750px; margin: 0 -24px -24px -24px; padding: 0;">
			<div bind:this={chartContainer} style="margin: 0; padding: 0;"></div>
		</div>

		<!-- ROC Chart Container -->
		<div class="overflow-hidden mt-2" style="height: 200px; margin: 0 -24px -24px -24px; padding: 0;">
			<div bind:this={rocChartContainer} style="margin: 0; padding: 0;"></div>
		</div>
	</div>
</div>

<style>
	.container {
		max-width: 2200px;
	}
</style>
