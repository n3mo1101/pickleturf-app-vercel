from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Usage: {{ my_dict|get_item:key }}"""
    return dictionary.get(key)

@register.filter
def get_slot_price(time_str):
    """Return price for a slot given its HH:MM:SS string."""
    from datetime import datetime
    from bookings.services import get_price_for_display
    try:
        t = datetime.strptime(time_str, '%H:%M:%S').time()
        return get_price_for_display(t)
    except Exception:
        return 0

@register.filter
def tx_desc(description):
    """Strip the legacy type prefix from a transaction description."""
    from transactions.utils import strip_tx_prefix
    return strip_tx_prefix(description)