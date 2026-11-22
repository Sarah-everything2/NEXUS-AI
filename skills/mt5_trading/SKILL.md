# MT5 Trading Skill

## Purpose
Integrate the existing Hermes AI-Trading / MetaTrader 5 bridge into NEXUS AI.

## Existing Integration
- Bridge: C:\AI-Trading\mt5-bridge
- API: http://127.0.0.1:8001
- Broker: Headway Demo
- Primary instrument: XAUUSD
- Strategy: Donchian 20 breakout with SMA 200 and ATR 14.
- Timeframe: H4.

## Initial Capabilities
1. Read account balance, equity and currency.
2. Retrieve market prices.
3. Inspect open positions.
4. Retrieve the latest strategy signal.

## API Endpoints
- GET /account
- GET /price/{symbol}
- GET /positions

## Safety Restrictions
- Read-only integration by default.
- Never expose trade execution through this skill.
- Never enable live trading automatically.
- Preserve Hermes trading_safety.json settings.
- Require human approval for consequential actions.
- Protect broker credentials and account information.

## Future Development
- AI market analysis.
- Strategy performance monitoring.
- Trading alerts.
- Demo execution only after separate security review.
- MT5 risk management integration.

## Important
NEXUS AI must reuse the existing Hermes bridge rather than create a duplicate MT5 connection.
