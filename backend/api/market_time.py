"""
Market Time API - Simplified
Only checks: is trading day, market hours, next trading session.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime

from backend.services.market_calendar import (
    get_market_calendar,
    get_market_status,
    is_trading_day as check_trading_day,
    get_current_ist_time,
    get_next_trading_day as get_next_trading_session
)
from backend.schemas import MarketStatusResponse

router = APIRouter(prefix="/api/market-time", tags=["market-time"])


@router.get("/status", response_model=MarketStatusResponse)
async def get_status():
    """Get current market status"""
    try:
        status = get_market_status()
        return MarketStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/is-trading-day")
async def check_trading_day_endpoint(
    date: Optional[str] = Query(None, description="Date to check (YYYY-MM-DD), defaults to today")
):
    """Check if a date is a trading day"""
    try:
        if date:
            try:
                check_date = datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            check_date = get_current_ist_time()
        
        is_trading = check_trading_day(check_date)
        is_weekend = check_date.weekday() >= 5
        
        return {
            "date": check_date.strftime('%Y-%m-%d'),
            "is_trading_day": is_trading,
            "is_weekend": is_weekend,
            "day_of_week": check_date.strftime('%A')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/next-trading-day")
async def get_next_trading_day(
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD), defaults to today")
):
    """Get the next trading day after a given date"""
    try:
        if from_date:
            try:
                start_date = datetime.strptime(from_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            start_date = get_current_ist_time()
        
        next_trading = get_next_trading_session(start_date)
        
        if not next_trading:
            raise HTTPException(status_code=404, detail="No trading day found in next 30 days")
        
        return {
            "from_date": start_date.strftime('%Y-%m-%d'),
            "next_trading_day": next_trading,
            "day_of_week": datetime.strptime(next_trading, '%Y-%m-%d').strftime('%A')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
