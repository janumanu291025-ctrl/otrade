/**
 * Format currency values
 */
export function formatCurrency(value, decimals = 2) {
    return new Intl.NumberFormat('en-IN', {
        style: 'decimal',
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

/**
 * Format percentage values
 */
export function formatPercentage(value, decimals = 2) {
    return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`;
}

/**
 * Format date and time
 */
export function formatDateTime(dateString) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

/**
 * Format time only
 */
export function formatTime(dateString) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    }).format(date);
}

/**
 * Get status badge class
 */
export function getStatusBadge(status) {
    const statusMap = {
        'active': 'badge-success',
        'stopped': 'badge-danger',
        'pending': 'badge-warning',
        'complete': 'badge-success',
        'rejected': 'badge-danger',
        'cancelled': 'badge-secondary'
    };
    return statusMap[status.toLowerCase()] || 'badge-info';
}

/**
 * Get trend color class
 */
export function getTrendColor(value) {
    if (value > 0) return 'text-green-600';
    if (value < 0) return 'text-red-600';
    return 'text-gray-600';
}

/**
 * Debounce function
 */
export function debounce(func, wait) {
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
 * Deep clone object
 */
export function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Check if market is open
 */
export function isMarketOpen() {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const day = now.getDay();
    
    // Market hours: 9:15 AM to 3:30 PM, Monday to Friday
    if (day === 0 || day === 6) return false; // Weekend
    
    const currentTime = hours * 60 + minutes;
    const marketOpen = 9 * 60 + 15; // 9:15 AM
    const marketClose = 15 * 60 + 30; // 3:30 PM
    
    return currentTime >= marketOpen && currentTime <= marketClose;
}

/**
 * Validate strategy configuration
 */
export function validateStrategy(strategy) {
    const errors = [];
    
    if (!strategy.name || strategy.name.trim() === '') {
        errors.push('Strategy name is required');
    }
    
    if (!strategy.broker_type) {
        errors.push('Broker type is required');
    }
    
    if (strategy.ma_short <= 0 || strategy.ma_long <= 0) {
        errors.push('Moving average periods must be positive');
    }
    
    if (strategy.ma_short >= strategy.ma_long) {
        errors.push('Short MA period must be less than long MA period');
    }
    
    if (strategy.sell_target_percentage <= 0) {
        errors.push('Sell target percentage must be positive');
    }
    
    if (strategy.strike_gap_points < 0) {
        errors.push('Strike gap points must be non-negative');
    }
    
    return {
        valid: errors.length === 0,
        errors
    };
}
