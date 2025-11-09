# OTrade - HFT Live Trading Engine Project Brief

## Project Overview
OTrade is a high-frequency trading (HFT) platform designed for live algorithmic trading in Indian markets. The system has been transformed from a database-dependent architecture to a zero-database, JSON-based, HFT-optimized solution.

## Core Requirements
- **Zero Database Architecture**: Eliminate all database dependencies for maximum performance
- **HFT Performance**: Sub-millisecond order processing and signal detection
- **JSON Configuration**: Human-readable, version-controllable configuration system
- **Real-time Trading**: Live LTP-based crossover detection and order execution
- **Risk Management**: Automatic bracket orders with target/stoploss functionality
- **Market Compliance**: Strict market hours enforcement and token expiry handling

## Success Criteria
- 25-50x performance improvement over database version
- Sub-millisecond processing (< 5μs for calculations, < 10μs for signals)
- Zero external dependencies (no database setup required)
- Production-ready HFT capabilities
- Stateless architecture allowing instant restarts

## Architecture Goals
- **Stateless Design**: No persistent state requirements
- **Scalable**: No database bottlenecks
- **Maintainable**: Pure Python with clear separation of concerns
- **Testable**: Easy mocking for comprehensive testing
- **Deployable**: Single binary with JSON configurations

## Key Components
1. **JSON Configuration Infrastructure** - ConfigManager with orjson processing
2. **HFT-Optimized Calculations** - 12 Numba JIT-compiled functions
3. **Zero-Database Live Trading Engine** - In-memory position tracking
4. **Real-time Signal Processing** - LTP-based crossover detection
5. **Risk Management System** - Automatic bracket order placement

## Performance Targets
- Config loading: < 1ms (vs 50ms DB)
- Price calculations: < 5μs (vs 200μs Python)
- Signal detection: < 10μs (vs 500μs Python)
- Memory usage: 80% reduction
- Startup time: Near instant
