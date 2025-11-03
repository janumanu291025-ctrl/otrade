"""Fund allocation and management"""
from typing import Dict, Optional
from sqlalchemy.orm import Session
from backend.models import Fund, Position
from backend.config import settings
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class FundManager:
    """Manage fund allocation and P&L calculations"""
    
    def __init__(self, db: Session, broker_client):
        self.db = db
        self.broker = broker_client
        self.max_fund_per_trade_pct = settings.MAX_FUND_PERCENTAGE_PER_TRADE
    
    def get_or_create_today_fund(self) -> Fund:
        """Get or create fund entry for today"""
        today = date.today()
        fund = self.db.query(Fund).filter(
            Fund.date >= datetime.combine(today, datetime.min.time()),
            Fund.date < datetime.combine(today, datetime.max.time())
        ).first()
        
        if not fund:
            # Create new fund entry
            try:
                broker_funds = self.broker.get_funds()
                
                # Extract available balance (broker-specific logic)
                if hasattr(broker_funds, 'get'):
                    # Kite format
                    equity = broker_funds.get("equity", {})
                    available_balance = equity.get("available", {}).get("live_balance", 0)
                else:
                    # Generic format
                    available_balance = 0
                
                fund = Fund(
                    date=datetime.now(),
                    opening_balance=available_balance,
                    available_balance=available_balance,
                    utilized_margin=0.0,
                    floating_pnl=0.0,
                    realized_pnl=0.0,
                    charges=0.0
                )
                self.db.add(fund)
                self.db.commit()
                self.db.refresh(fund)
                
            except Exception as e:
                logger.error(f"Error creating fund entry: {str(e)}")
                # Fallback with default values
                fund = Fund(
                    date=datetime.now(),
                    opening_balance=0,
                    available_balance=0
                )
                self.db.add(fund)
                self.db.commit()
                self.db.refresh(fund)
        
        return fund
    
    def update_fund_from_broker(self) -> Fund:
        """Update fund information from broker"""
        fund = self.get_or_create_today_fund()
        
        try:
            broker_funds = self.broker.get_funds()
            
            # Update available balance
            if hasattr(broker_funds, 'get'):
                equity = broker_funds.get("equity", {})
                fund.available_balance = equity.get("available", {}).get("live_balance", fund.available_balance)
                fund.utilized_margin = equity.get("utilised", {}).get("debits", 0)
            
            self.db.commit()
            self.db.refresh(fund)
            
        except Exception as e:
            logger.error(f"Error updating fund from broker: {str(e)}")
        
        return fund
    
    def calculate_floating_pnl(self, broker_client) -> float:
        """Calculate floating P&L from open positions"""
        try:
            positions = self.db.query(Position).filter(
                Position.closed_at.is_(None)
            ).all()
            
            if not positions:
                return 0.0
            
            # Get current prices
            instrument_keys = [pos.instrument_token for pos in positions]
            ltp_data = broker_client.get_ltp(instrument_keys)
            
            total_pnl = 0.0
            for position in positions:
                current_price = ltp_data.get(position.instrument_token, position.last_price)
                pnl = (current_price - position.average_price) * position.quantity
                total_pnl += pnl
                
                # Update position
                position.last_price = current_price
                position.pnl = pnl
                position.pnl_percentage = (pnl / (position.average_price * position.quantity)) * 100
            
            self.db.commit()
            return total_pnl
            
        except Exception as e:
            logger.error(f"Error calculating floating P&L: {str(e)}")
            return 0.0
    
    def update_floating_pnl(self, broker_client) -> Fund:
        """Update fund with floating P&L"""
        fund = self.get_or_create_today_fund()
        fund.floating_pnl = self.calculate_floating_pnl(broker_client)
        self.db.commit()
        self.db.refresh(fund)
        return fund
    
    def calculate_max_trade_amount(self) -> float:
        """Calculate maximum amount that can be allocated to one trade (16% rule)"""
        fund = self.get_or_create_today_fund()
        
        # Calculate current fund value
        current_fund = fund.opening_balance + fund.realized_pnl + fund.floating_pnl - fund.charges
        
        max_amount = current_fund * (self.max_fund_per_trade_pct / 100.0)
        return max_amount
    
    def can_place_trade(self, required_amount: float) -> bool:
        """
        Check if trade can be placed based on fund allocation rules
        
        Args:
            required_amount: Amount required for the trade
            
        Returns:
            True if trade can be placed, False otherwise
        """
        max_amount = self.calculate_max_trade_amount()
        fund = self.get_or_create_today_fund()
        
        # Check if required amount is within limit
        if required_amount > max_amount:
            logger.warning(
                f"Trade amount {required_amount} exceeds max allocation {max_amount} "
                f"({self.max_fund_per_trade_pct}% of fund)"
            )
            return False
        
        # Check if sufficient available balance
        if required_amount > fund.available_balance:
            logger.warning(
                f"Insufficient balance: required {required_amount}, available {fund.available_balance}"
            )
            return False
        
        return True
    
    def record_trade_charges(self, charges: float):
        """Record trading charges (brokerage, taxes, etc.)"""
        fund = self.get_or_create_today_fund()
        fund.charges += charges
        self.db.commit()
    
    def record_realized_pnl(self, pnl: float):
        """Record realized P&L from closed position"""
        fund = self.get_or_create_today_fund()
        fund.realized_pnl += pnl
        self.db.commit()
    
    def get_fund_summary(self, broker_client) -> Dict:
        """Get comprehensive fund summary"""
        fund = self.get_or_create_today_fund()
        floating_pnl = self.calculate_floating_pnl(broker_client)
        
        current_value = fund.opening_balance + fund.realized_pnl + floating_pnl - fund.charges
        max_trade_amount = self.calculate_max_trade_amount()
        
        return {
            "opening_balance": fund.opening_balance,
            "available_balance": fund.available_balance,
            "utilized_margin": fund.utilized_margin,
            "floating_pnl": floating_pnl,
            "realized_pnl": fund.realized_pnl,
            "charges": fund.charges,
            "current_value": current_value,
            "total_pnl": fund.realized_pnl + floating_pnl,
            "max_trade_amount": max_trade_amount,
            "max_trade_percentage": self.max_fund_per_trade_pct
        }
