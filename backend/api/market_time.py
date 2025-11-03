"""
Market Time API Endpoints
==========================

REST API for market timing configuration and status checks.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from backend.database import get_db
from backend.services.market_time import get_market_time_service
from backend.schemas import (
    MarketHoursConfig,
    MarketHoursUpdate,
    HolidayCreate,
    HolidayResponse,
    MarketStatusResponse,
    TimeUntilResponse
)

router = APIRouter(prefix="/api/market-time", tags=["market-time"])


# ==================== Configuration Endpoints ====================

@router.get("/config", response_model=MarketHoursConfig)
async def get_market_config(db: Session = Depends(get_db)):
    """
    Get current market hours configuration
    
    Returns configuration including:
    - Market open/close times
    - Webhook start time
    - Order placement window
    - Square-off time
    - Trading days
    - Polling interval
    """
    try:
        service = get_market_time_service(db)
        config = service.get_config()
        
        # Parse trading_days if it's a JSON string
        import json
        trading_days = config.trading_days
        if isinstance(trading_days, str):
            trading_days = json.loads(trading_days)
        
        return MarketHoursConfig(
            id=config.id,
            start_time=config.start_time,
            end_time=config.end_time,
            webhook_start_time=config.webhook_start_time,
            order_placement_start_time=config.order_placement_start_time,
            order_placement_end_time=config.order_placement_end_time,
            square_off_time=config.square_off_time,
            trading_days=trading_days,
            webhook_url=config.webhook_url,
            polling_interval_seconds=config.polling_interval_seconds
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting market config: {str(e)}")


@router.put("/config", response_model=MarketHoursConfig)
async def update_market_config(
    update: MarketHoursUpdate,
    db: Session = Depends(get_db)
):
    """
    Update market hours configuration
    
    Allows updating:
    - Market hours (start/end times)
    - Webhook start time
    - Order placement window
    - Square-off time
    - Trading days
    - Webhook configuration
    - Polling configuration
    """
    try:
        service = get_market_time_service(db)
        
        # Validate time formats (HH:MM)
        time_fields = {
            'start_time': update.start_time,
            'end_time': update.end_time,
            'webhook_start_time': update.webhook_start_time,
            'order_placement_start_time': update.order_placement_start_time,
            'order_placement_end_time': update.order_placement_end_time,
            'square_off_time': update.square_off_time
        }
        
        for field_name, field_value in time_fields.items():
            if field_value is not None:
                try:
                    datetime.strptime(field_value, '%H:%M')
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid time format for {field_name}. Use HH:MM"
                    )
        
        # Validate trading days
        if update.trading_days is not None:
            if not all(0 <= day <= 6 for day in update.trading_days):
                raise HTTPException(
                    status_code=400,
                    detail="Trading days must be between 0 (Monday) and 6 (Sunday)"
                )
        
        config = service.update_config(
            start_time=update.start_time,
            end_time=update.end_time,
            webhook_start_time=update.webhook_start_time,
            order_placement_start_time=update.order_placement_start_time,
            order_placement_end_time=update.order_placement_end_time,
            square_off_time=update.square_off_time,
            trading_days=update.trading_days,
            webhook_url=update.webhook_url,
            polling_interval_seconds=update.polling_interval_seconds
        )
        
        # Parse trading_days for response
        import json
        trading_days = config.trading_days
        if isinstance(trading_days, str):
            trading_days = json.loads(trading_days)
        
        return MarketHoursConfig(
            id=config.id,
            start_time=config.start_time,
            end_time=config.end_time,
            webhook_start_time=config.webhook_start_time,
            order_placement_start_time=config.order_placement_start_time,
            order_placement_end_time=config.order_placement_end_time,
            square_off_time=config.square_off_time,
            trading_days=trading_days,
            webhook_url=config.webhook_url,
            polling_interval_seconds=config.polling_interval_seconds
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating market config: {str(e)}")


# ==================== Status Endpoints ====================

@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status(db: Session = Depends(get_db)):
    """
    Get current market status
    
    Returns:
    - Whether market is currently open
    - Whether webhook connection is active
    - Whether order placement is allowed
    - Whether it's square-off time
    - Current time and day
    - Market hours configuration
    - Next trading day if market is closed
    """
    try:
        service = get_market_time_service(db)
        status = service.get_market_status()
        
        return MarketStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting market status: {str(e)}")


@router.get("/time-until-open", response_model=TimeUntilResponse)
async def get_time_until_open(db: Session = Depends(get_db)):
    """
    Get time remaining until market opens
    
    Returns:
    - Seconds until market opens
    - Human-readable format
    - Next market open time
    """
    try:
        service = get_market_time_service(db)
        time_info = service.time_until_market_open()
        
        return TimeUntilResponse(**time_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating time until open: {str(e)}")


@router.get("/time-until-close", response_model=TimeUntilResponse)
async def get_time_until_close(db: Session = Depends(get_db)):
    """
    Get time remaining until market closes
    
    Returns:
    - Seconds until market closes
    - Human-readable format
    - Market close time
    """
    try:
        service = get_market_time_service(db)
        time_info = service.time_until_market_close()
        
        return TimeUntilResponse(**time_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating time until close: {str(e)}")


# ==================== Holiday Endpoints ====================

@router.get("/holidays", response_model=List[HolidayResponse])
async def get_holidays(
    year: Optional[int] = Query(None, description="Filter holidays by year"),
    db: Session = Depends(get_db)
):
    """
    Get list of holidays
    
    Args:
        year: Optional year filter
    
    Returns:
        List of holidays
    """
    try:
        service = get_market_time_service(db)
        holidays = service.get_holidays(year)
        
        return [
            HolidayResponse(
                id=h.id,
                date=h.date,
                name=h.name,
                description=h.description,
                created_at=h.created_at
            )
            for h in holidays
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting holidays: {str(e)}")


@router.post("/holidays", response_model=HolidayResponse)
async def add_holiday(
    holiday: HolidayCreate,
    db: Session = Depends(get_db)
):
    """
    Add a new holiday
    
    Args:
        holiday: Holiday details
    
    Returns:
        Created holiday
    """
    try:
        # Validate date format
        try:
            datetime.strptime(holiday.date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        service = get_market_time_service(db)
        new_holiday = service.add_holiday(holiday.date, holiday.name, holiday.description)
        
        return HolidayResponse(
            id=new_holiday.id,
            date=new_holiday.date,
            name=new_holiday.name,
            description=new_holiday.description,
            created_at=new_holiday.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding holiday: {str(e)}")


@router.delete("/holidays/{date}")
async def remove_holiday(
    date: str,
    db: Session = Depends(get_db)
):
    """
    Remove a holiday by date
    
    Args:
        date: Holiday date (YYYY-MM-DD format)
    
    Returns:
        Success message
    """
    try:
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        service = get_market_time_service(db)
        removed = service.remove_holiday(date)
        
        if not removed:
            raise HTTPException(status_code=404, detail=f"Holiday not found for date: {date}")
        
        return {"status": "success", "message": f"Holiday on {date} removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing holiday: {str(e)}")


# ==================== Utility Endpoints ====================

@router.get("/is-trading-day")
async def check_is_trading_day(
    date: Optional[str] = Query(None, description="Date to check (YYYY-MM-DD), defaults to today"),
    db: Session = Depends(get_db)
):
    """
    Check if a specific date is a trading day
    
    Args:
        date: Date to check (YYYY-MM-DD format), defaults to today
    
    Returns:
        Whether the date is a trading day
    """
    try:
        service = get_market_time_service(db)
        
        if date:
            # Validate and parse date
            try:
                check_date = datetime.strptime(date, '%Y-%m-%d')
                check_date = service.convert_to_ist(check_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            check_date = service.get_current_ist_time()
        
        is_trading = service.is_trading_day(check_date)
        is_holiday = service.is_holiday(check_date)
        is_weekend = check_date.weekday() >= 5
        
        return {
            "date": check_date.strftime('%Y-%m-%d'),
            "is_trading_day": is_trading,
            "is_holiday": is_holiday,
            "is_weekend": is_weekend,
            "day_of_week": check_date.strftime('%A')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking trading day: {str(e)}")


@router.get("/next-trading-day")
async def get_next_trading_day(
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD), defaults to today"),
    db: Session = Depends(get_db)
):
    """
    Get the next trading day after a given date
    
    Args:
        from_date: Start date (YYYY-MM-DD format), defaults to today
    
    Returns:
        Next trading day information
    """
    try:
        service = get_market_time_service(db)
        
        if from_date:
            # Validate and parse date
            try:
                start_date = datetime.strptime(from_date, '%Y-%m-%d')
                start_date = service.convert_to_ist(start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            start_date = service.get_current_ist_time()
        
        # Find next trading day
        next_day = start_date + timedelta(days=1)
        for _ in range(10):  # Check next 10 days
            if service.is_trading_day(next_day):
                return {
                    "from_date": start_date.strftime('%Y-%m-%d'),
                    "next_trading_day": next_day.strftime('%Y-%m-%d'),
                    "days_until": (next_day.date() - start_date.date()).days,
                    "day_of_week": next_day.strftime('%A')
                }
            next_day = next_day + timedelta(days=1)
        
        raise HTTPException(status_code=404, detail="No trading day found in the next 10 days")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding next trading day: {str(e)}")
