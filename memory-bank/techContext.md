# OTrade - Technical Context

## Technology Stack

### Core Technologies
- **Python 3.9+**: Primary development language
- **Numba**: JIT compilation for HFT performance (25-50x speedup)
- **orjson**: Ultra-fast JSON processing (10x faster than standard json)
- **NumPy**: Vectorized mathematical operations
- **FastAPI**: High-performance async web framework
- **WebSocket**: Real-time communication for live trading updates

### Frontend Technologies
- **Svelte**: Reactive frontend framework
- **Tailwind CSS**: Utility-first CSS framework
- **Vite**: Fast build tool and development server
- **TypeScript**: Type-safe JavaScript development

### Broker Integration
- **Kite Connect**: Zerodha's trading API
- **Upstox API**: Alternative broker integration
- **Unified Broker Middleware**: Abstracted broker interface

## Development Setup

### Environment Requirements
- **Python 3.9+**: Required for Numba compatibility
- **pip**: Package management
- **git**: Version control
- **VS Code**: Recommended IDE with Python extensions

### Key Dependencies
```python
# Core HFT Dependencies
numba>=0.56.0          # JIT compilation
orjson>=3.8.0          # Fast JSON processing
numpy>=1.21.0          # Vectorized operations

# Web Framework
fastapi>=0.100.0       # Async API framework
uvicorn>=0.20.0        # ASGI server

# Broker APIs
kiteconnect>=4.3.0     # Zerodha Kite API
upstox-python-sdk>=1.0.0  # Upstox API

# Utilities
pydantic>=2.0.0        # Data validation
python-dotenv>=1.0.0   # Environment variables
websockets>=11.0.0     # WebSocket support
```

### Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py

# Run tests
python test_hft_engine.py

# Frontend development
cd frontend && npm run dev
```

## Technical Constraints

### Performance Requirements
- **Config Loading**: < 1ms (50x faster than DB)
- **Price Calculations**: < 5μs per operation
- **Signal Detection**: < 10μs per analysis
- **Order Placement**: < 1ms end-to-end
- **Memory Usage**: < 100MB baseline

### System Limitations
- **No Database**: All state must be in-memory or JSON files
- **Stateless Design**: No persistent state between restarts
- **Real-time Processing**: Must handle live price feeds without blocking
- **Market Hours**: Strict 9:15 AM - 3:30 PM IST compliance
- **API Rate Limits**: Respect broker API limitations

### Hardware Requirements
- **CPU**: Multi-core processor for parallel processing
- **RAM**: Minimum 4GB, recommended 8GB+
- **Network**: Stable internet connection for broker APIs
- **Storage**: Minimal (JSON configs only)

## Tool Usage Patterns

### Code Organization
```
backend/
├── core/           # HFT calculations (Numba JIT)
├── services/       # Business logic
├── api/           # FastAPI endpoints
├── broker/        # Broker integrations
└── utils/         # Utilities

config/             # JSON configuration system
frontend/           # Svelte web interface
memory-bank/        # Project documentation
```

### Development Workflow
1. **Configuration**: All settings in JSON files under `config/`
2. **Calculations**: Performance-critical code in `backend/core/calculations.py`
3. **Trading Logic**: Business rules in `backend/services/`
4. **API Layer**: REST/WebSocket endpoints in `backend/api/`
5. **Testing**: Comprehensive tests in `test_hft_engine.py`

### Performance Optimization Patterns
- **Numba JIT**: All math operations compiled to machine code
- **Vectorization**: NumPy arrays for batch processing
- **Async Processing**: Non-blocking I/O operations
- **Memory Pooling**: Reuse objects to reduce GC pressure
- **Pre-compilation**: JIT functions compiled on import

### Error Handling Patterns
- **Graceful Degradation**: Continue operation on non-critical failures
- **Token Expiry**: Auto-pause trading on authentication issues
- **Rate Limiting**: Respect API limits with exponential backoff
- **Logging**: Comprehensive logging for debugging and monitoring

## Build and Deployment

### Build Process
```bash
# Backend build (JIT compilation happens at runtime)
python -c "import backend.core.calculations"

# Frontend build
cd frontend && npm run build

# Production run
python run.py
```

### Deployment Considerations
- **Single Binary**: No external database dependencies
- **Configuration**: JSON files for environment-specific settings
- **Monitoring**: Built-in performance metrics
- **Logging**: Structured logging for production monitoring
- **Health Checks**: API endpoints for system monitoring

## Testing Strategy

### Unit Testing
- **Calculation Functions**: Test Numba JIT accuracy
- **Configuration Loading**: Test JSON parsing and validation
- **Trading Logic**: Test signal detection and order placement

### Integration Testing
- **Broker APIs**: Mock external API calls
- **WebSocket Communication**: Test real-time data flow
- **End-to-End**: Full trading cycle simulation

### Performance Testing
- **Benchmarking**: Compare against baseline performance
- **Load Testing**: Simulate high-frequency price updates
- **Memory Profiling**: Monitor memory usage patterns
