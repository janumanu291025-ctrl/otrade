"""Option contract selection logic for Nifty options"""
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.models import Instrument
import logging

logger = logging.getLogger(__name__)


class ContractSelector:
    """Select appropriate option contracts based on strategy"""
    
    def __init__(self, db: Session):
        """
        Initialize with database session
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def get_nearest_expiry(self, index: str) -> Optional[str]:
        """Get nearest expiry date for the given index"""
        try:
            # Query instruments for the index with expiry dates
            instruments = self.db.query(Instrument).filter(
                Instrument.name.like(f"%{index}%"),
                Instrument.expiry.isnot(None)
            ).all()
            
            if not instruments:
                return None
            
            # Get unique expiry dates and sort
            expiry_dates = sorted(set(inst.expiry for inst in instruments if inst.expiry))
            
            if not expiry_dates:
                return None
            
            # Return nearest expiry
            return expiry_dates[0]
            
        except Exception as e:
            logger.error(f"Error getting nearest expiry: {e}")
            return None
    
    def get_option_contract(
        self,
        index: str,
        expiry: str,
        strike: int,
        option_type: str
    ) -> Optional[Instrument]:
        """
        Get specific option contract from database
        
        Args:
            index: Index name (NIFTY, BANKNIFTY)
            expiry: Expiry date string
            strike: Strike price
            option_type: CE or PE
            
        Returns:
            Instrument object or None
        """
        try:
            # Build tradingsymbol pattern
            # Example: NIFTY25N0426000CE
            symbol_pattern = f"{index}%{strike}{option_type}"
            
            contract = self.db.query(Instrument).filter(
                Instrument.tradingsymbol.like(symbol_pattern),
                Instrument.expiry == expiry,
                Instrument.strike == float(strike)
            ).first()
            
            return contract
            
        except Exception as e:
            logger.error(f"Error getting option contract: {e}")
            return None

