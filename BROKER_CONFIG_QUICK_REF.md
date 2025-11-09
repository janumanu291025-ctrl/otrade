# Broker Configuration - Quick Reference

## Configuration is Now Exclusively in `.env`

### Broker Type Selection
```env
BROKER_TYPE=kite  # or 'upstox'
```

### Kite Broker (Zerodha)
```env
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
KITE_ACCESS_TOKEN=your_access_token
KITE_USER_ID=your_user_id
KITE_PASSWORD=your_password
KITE_REDIRECT_URL=http://localhost:8000/callback
KITE_POSTBACK_URL=https://your-ngrok-url/postback
```

### Upstox Broker (Optional)
```env
UPSTOX_API_KEY=your_api_key
UPSTOX_API_SECRET=your_api_secret
UPSTOX_ACCESS_TOKEN=your_access_token
UPSTOX_USER_ID=your_user_id
UPSTOX_PASSWORD=your_password
```

## How to Update Broker Config

### 1. Update Static Credentials
Edit `.env` file directly:
```bash
nano .env
# OR
vim .env
```

### 2. Update Access Token After Authentication
Access token is automatically updated when user authenticates through the UI:
- Frontend calls OAuth flow
- Backend receives callback and updates `.env` with new token
- No manual intervention needed

### 3. Access Config in Backend Code

**Old Way (Deprecated):**
```python
from config.manager import ConfigManager
config_manager = ConfigManager()
broker_config = config_manager.load_broker_config()
```

**New Way (Recommended):**
```python
from backend.config import settings

# Get broker type
broker_type = settings.BROKER_TYPE  # "kite" or "upstox"

# Get Kite credentials
api_key = settings.KITE_API_KEY
api_secret = settings.KITE_API_SECRET
access_token = settings.KITE_ACCESS_TOKEN

# Get Upstox credentials
api_key = settings.UPSTOX_API_KEY
api_secret = settings.UPSTOX_API_SECRET
access_token = settings.UPSTOX_ACCESS_TOKEN
```

## API Endpoints

### Get Broker Status
```bash
GET /api/broker/status/kite
```
Response includes: connected, token_expired, market_active, etc.

### Get Environment Config
```bash
GET /api/broker/env-config/kite
```
Returns current config from .env (no secrets)

### Get Auth URL (for login)
```bash
GET /api/broker/auth-url/kite
```
Returns OAuth URL for user to authenticate

### Authenticate (called after OAuth callback)
```bash
GET /api/broker/callback?request_token=xxx&broker_type=kite
```
Automatically updates .env with access token

### Get Profile
```bash
GET /api/broker/profile/kite
```
Requires valid access token in .env

### Get Funds
```bash
GET /api/broker/funds/kite
```

### Disconnect Broker
```bash
POST /api/broker/disconnect/kite
```
Clears access token from .env

## Troubleshooting

### "Broker not configured"
**Solution**: Ensure `BROKER_TYPE` and `{BROKER_TYPE}_API_KEY` and `{BROKER_TYPE}_API_SECRET` are set in `.env`

### "Broker not authenticated"
**Solution**: Access token is missing or expired. Complete OAuth flow or update `{BROKER_TYPE}_ACCESS_TOKEN` in `.env`

### Access token not persisting
**Solution**: Check that `.env` file is writable and backend has permission to write to it

### Settings not updating
**Solution**: Restart backend application to reload `.env` file after manual edits

## No JSON Config Needed

✓ `config/broker_config.json` is no longer needed - DELETED
✓ All configuration is now in `.env` file
✓ Simpler, cleaner, more secure

## Key Classes/Functions

- `backend.config.Settings` - Pydantic settings that loads from .env
- `backend.config.settings` - Global settings instance
- `backend.broker.factory.get_broker_client()` - Get broker client using settings
- `backend.api.broker.get_broker_settings_config()` - Get broker config dict from settings
