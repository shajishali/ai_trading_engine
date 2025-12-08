"""
Custom template filters for better price formatting
"""

from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def smart_price(value):
    """Format price with appropriate decimal places based on value size"""
    if not value:
        return 'N/A'
    
    try:
        # Convert to Decimal for precise handling
        if isinstance(value, str):
            price = Decimal(value)
        elif isinstance(value, (int, float)):
            price = Decimal(str(value))
        else:
            price = Decimal(str(value))
        
        # Handle very small prices (like BONK, PEPE, etc.)
        if price < Decimal('0.0001'):
            # For prices less than 0.0001, show up to 8 decimal places
            formatted = f"{price:.8f}".rstrip('0').rstrip('.')
        elif price < Decimal('0.01'):
            # For prices less than 0.01, show up to 6 decimal places
            formatted = f"{price:.6f}".rstrip('0').rstrip('.')
        elif price < Decimal('1'):
            # For prices less than 1, show up to 4 decimal places
            formatted = f"{price:.4f}".rstrip('0').rstrip('.')
        elif price < Decimal('100'):
            # For prices less than 100, show up to 3 decimal places
            formatted = f"{price:.3f}".rstrip('0').rstrip('.')
        else:
            # For prices 100+, show up to 2 decimal places
            formatted = f"{price:.2f}".rstrip('0').rstrip('.')
        
        return formatted
        
    except (ValueError, TypeError, AttributeError):
        return 'N/A'

@register.filter
def price_with_symbol(value):
    """Format price with dollar sign and smart formatting"""
    formatted_price = smart_price(value)
    if formatted_price == 'N/A':
        return 'N/A'
    return f"${formatted_price}"















































