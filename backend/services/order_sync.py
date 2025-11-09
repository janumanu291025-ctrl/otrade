"""
Order Sync Service
Syncs orders from broker API to database and calculates trade statistics
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.models import Order
from backend.broker.base import BaseBroker
from backend.services.market_calendar import (
    is_market_open,
    get_market_status
)

logger = logging.getLogger(__name__)


class OrderSyncService:
    """Service to sync orders from broker and calculate statistics"""
    
    def __init__(self, db: Session, broker: BaseBroker):
        self.db = db
        self.broker = broker
    
    async def sync_orders_from_broker(self, strategy_id: Optional[int] = None) -> Dict:
        """
        Fetch orders from broker API and sync to database
        Returns summary of sync operation
        """
        try:
            import asyncio
            
            # Fetch all orders from broker
            broker_orders = await asyncio.to_thread(self.broker.get_orders)
            
            synced_count = 0
            updated_count = 0
            skipped_count = 0
            
            for broker_order in broker_orders:
                order_id = broker_order.get('order_id')
                if not order_id:
                    continue
                
                # Check if order exists in database
                existing_order = self.db.query(Order).filter(
                    Order.broker_order_id == order_id
                ).first()
                
                if existing_order:
                    # Update existing order
                    updated = self._update_order_from_broker_data(existing_order, broker_order)
                    if updated:
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    # Create new order from broker data
                    # Try to match with strategy if provided
                    if strategy_id:
                        new_order = self._create_order_from_broker_data(broker_order, strategy_id)
                        if new_order:
                            self.db.add(new_order)
                            synced_count += 1
            
            self.db.commit()
            
            logger.info(
                f"Order sync complete: {synced_count} new, {updated_count} updated, "
                f"{skipped_count} skipped"
            )
            
            return {
                "synced": synced_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "total_broker_orders": len(broker_orders)
            }
        
        except Exception as e:
            logger.error(f"Error syncing orders from broker: {e}")
            self.db.rollback()
            return {
                "error": str(e),
                "synced": 0,
                "updated": 0,
                "skipped": 0
            }
    
    def _update_order_from_broker_data(self, order: Order, broker_data: Dict) -> bool:
        """Update order with broker data, returns True if updated"""
        updated = False
        
        # Update status
        broker_status = broker_data.get('status', '').upper()
        new_status = self._map_broker_status(broker_status)
        if new_status and order.status != new_status:
            order.status = new_status
            updated = True
        
        # Update average price
        avg_price = broker_data.get('average_price', 0)
        if avg_price > 0 and order.average_price != avg_price:
            order.average_price = avg_price
            updated = True
        
        # Update filled time
        if new_status == 'completed' and not order.filled_at:
            order.filled_at = datetime.now()
            updated = True
        
        # Update exchange order ID
        exchange_order_id = broker_data.get('exchange_order_id')
        if exchange_order_id and order.exchange_order_id != exchange_order_id:
            order.exchange_order_id = exchange_order_id
            updated = True
        
        # Update status message
        status_msg = broker_data.get('status_message')
        if status_msg and order.status_message != status_msg:
            order.status_message = status_msg
            updated = True
        
        # Mark as synced
        if not order.synced_with_broker:
            order.synced_with_broker = True
            updated = True
        
        if updated:
            order.updated_at = datetime.now()
        
        return updated
    
    def _create_order_from_broker_data(self, broker_data: Dict, strategy_id: int) -> Optional[Order]:
        """Create new order from broker data"""
        try:
            order_id = broker_data.get('order_id')
            
            # Map broker status
            broker_status = broker_data.get('status', '').upper()
            status = self._map_broker_status(broker_status)
            
            # Map transaction type (BUY/SELL)
            transaction_type = broker_data.get('transaction_type', '').lower()
            
            # Create order
            order = Order(
                strategy_id=strategy_id,
                broker_order_id=order_id,
                exchange_order_id=broker_data.get('exchange_order_id'),
                instrument_token=str(broker_data.get('instrument_token', '')),
                symbol=broker_data.get('tradingsymbol', ''),
                exchange=broker_data.get('exchange', ''),
                order_type=transaction_type,  # buy or sell
                transaction_type=broker_data.get('order_type', 'LIMIT').lower(),  # limit or market
                product=broker_data.get('product', 'MIS'),
                quantity=broker_data.get('quantity', 0),
                price=broker_data.get('price', 0.0),
                average_price=broker_data.get('average_price', 0.0) or None,
                status=status,
                status_message=broker_data.get('status_message'),
                synced_with_broker=True,
                placed_at=broker_data.get('order_timestamp') or datetime.now(),
                filled_at=datetime.now() if status == 'completed' else None
            )
            
            return order
        except Exception as e:
            logger.error(f"Error creating order from broker data: {e}")
            return None
    
    def _map_broker_status(self, broker_status: str) -> str:
        """Map broker status to our internal status"""
        status_map = {
            'COMPLETE': 'completed',
            'REJECTED': 'rejected',
            'CANCELLED': 'cancelled',
            'OPEN': 'pending',
            'TRIGGER PENDING': 'pending',
            'PENDING': 'pending'
        }
        return status_map.get(broker_status, 'pending')
    
    def calculate_trade_statistics(self, strategy_id: int) -> Dict:
        """Calculate comprehensive trade statistics from database orders"""
        try:
            # Get all completed orders for strategy
            orders = self.db.query(Order).filter(
                and_(
                    Order.strategy_id == strategy_id,
                    Order.status == 'completed'
                )
            ).all()
            
            # Separate by option type (from symbol)
            call_orders = [o for o in orders if 'CE' in o.symbol]
            put_orders = [o for o in orders if 'PE' in o.symbol]
            
            # Calculate statistics for calls
            call_stats = self._calculate_option_stats(call_orders)
            
            # Calculate statistics for puts
            put_stats = self._calculate_option_stats(put_orders)
            
            # Calculate totals
            total_buy_value = call_stats['buy_value'] + put_stats['buy_value']
            total_sell_value = call_stats['sell_value'] + put_stats['sell_value']
            total_pnl = call_stats['pnl'] + put_stats['pnl']
            total_trades = call_stats['total_trades'] + put_stats['total_trades']
            
            # Calculate ROC (Return on Capital)
            roc = (total_pnl / total_buy_value * 100) if total_buy_value > 0 else 0.0
            
            return {
                'call': {
                    'buy': call_stats['buy_count'],
                    'sell': call_stats['sell_count'],
                    'buy_value': call_stats['buy_value'],
                    'sell_value': call_stats['sell_value'],
                    'total_value': call_stats['buy_value'],  # For display
                    'pnl': call_stats['pnl'],
                    'total_trades': call_stats['total_trades']
                },
                'put': {
                    'buy': put_stats['buy_count'],
                    'sell': put_stats['sell_count'],
                    'buy_value': put_stats['buy_value'],
                    'sell_value': put_stats['sell_value'],
                    'total_value': put_stats['buy_value'],  # For display
                    'pnl': put_stats['pnl'],
                    'total_trades': put_stats['total_trades']
                },
                'total': {
                    'trades': total_trades,
                    'value': total_buy_value,
                    'buy_value': total_buy_value,
                    'sell_value': total_sell_value,
                    'pnl': total_pnl,
                    'roc': roc
                }
            }
        
        except Exception as e:
            logger.error(f"Error calculating trade statistics: {e}")
            return self._empty_statistics()
    
    def _calculate_option_stats(self, orders: List[Order]) -> Dict:
        """Calculate statistics for a list of orders"""
        buy_orders = [o for o in orders if o.order_type == 'buy']
        sell_orders = [o for o in orders if o.order_type == 'sell']
        
        # Calculate buy value
        buy_value = sum(
            o.quantity * (o.average_price or o.price)
            for o in buy_orders
        )
        
        # Calculate sell value
        sell_value = sum(
            o.quantity * (o.average_price or o.price)
            for o in sell_orders
        )
        
        # Calculate P&L (sell - buy)
        pnl = sell_value - buy_value
        
        return {
            'buy_count': len(buy_orders),
            'sell_count': len(sell_orders),
            'buy_value': buy_value,
            'sell_value': sell_value,
            'pnl': pnl,
            'total_trades': len(orders)
        }
    
    def _empty_statistics(self) -> Dict:
        """Return empty statistics structure"""
        return {
            'call': {
                'buy': 0,
                'sell': 0,
                'buy_value': 0.0,
                'sell_value': 0.0,
                'total_value': 0.0,
                'pnl': 0.0,
                'total_trades': 0
            },
            'put': {
                'buy': 0,
                'sell': 0,
                'buy_value': 0.0,
                'sell_value': 0.0,
                'total_value': 0.0,
                'pnl': 0.0,
                'total_trades': 0
            },
            'total': {
                'trades': 0,
                'value': 0.0,
                'buy_value': 0.0,
                'sell_value': 0.0,
                'pnl': 0.0,
                'roc': 0.0
            }
        }
    
    def get_sync_strategy(self) -> Dict:
        """
        Determine the sync strategy based on market hours
        Returns dict with sync method and interval information
        """
        market_open = is_market_open()
        
        if market_open:
            sync_method = "webhook"
            sync_interval = None  # Real-time via webhook during market hours
        else:
            sync_method = "manual"
            sync_interval = None
        
        market_status = get_market_status()
        
        return {
            "method": sync_method,  # Changed from sync_method to method
            "sync_interval_seconds": sync_interval,
            "market_status": market_status,
            "recommendation": self._get_sync_recommendation(sync_method, market_open)
        }
    
    def _get_sync_recommendation(self, sync_method: str, market_active: bool) -> str:
        """Get human-readable recommendation for order sync"""
        if sync_method == "webhook":
            return "Using real-time webhook updates during market hours. Orders will update automatically."
        elif sync_method == "polling":
            return f"Market is closed. Using API polling to check order status periodically."
        else:
            return "Order sync is disabled. Use 'Sync Orders' button to manually fetch order status."
    
    async def sync_open_orders(self, strategy_id: Optional[int] = None) -> Dict:
        """
        Sync only open orders from broker
        This is more efficient than syncing all orders
        """
        try:
            import asyncio
            
            # Fetch orders from broker
            broker_orders = await asyncio.to_thread(self.broker.get_orders)
            
            # Filter only open orders
            open_statuses = ['OPEN', 'TRIGGER PENDING', 'PENDING']
            open_orders = [
                order for order in broker_orders 
                if order.get('status', '').upper() in open_statuses
            ]
            
            synced_count = 0
            updated_count = 0
            
            for broker_order in open_orders:
                order_id = broker_order.get('order_id')
                if not order_id:
                    continue
                
                # Check if order exists in database
                existing_order = self.db.query(Order).filter(
                    Order.broker_order_id == order_id
                ).first()
                
                if existing_order:
                    updated = self._update_order_from_broker_data(existing_order, broker_order)
                    if updated:
                        updated_count += 1
                else:
                    # Create new order from broker data
                    if strategy_id:
                        new_order = self._create_order_from_broker_data(broker_order, strategy_id)
                        if new_order:
                            self.db.add(new_order)
                            synced_count += 1
            
            self.db.commit()
            
            logger.info(
                f"Open order sync complete: {synced_count} new, {updated_count} updated, "
                f"{len(open_orders)} total open orders"
            )
            
            return {
                "synced": synced_count,
                "updated": updated_count,
                "total_open_orders": len(open_orders),
                "sync_method": self.get_sync_strategy()["sync_method"]
            }
        
        except Exception as e:
            logger.error(f"Error syncing open orders: {e}")
            self.db.rollback()
            return {
                "error": str(e),
                "synced": 0,
                "updated": 0
            }
