"""Shared helpers for transaction display."""

# Legacy type prefixes that were prepended to descriptions.
# The tx_type column already conveys this — strip it on display.
TX_PREFIXES = (
    'Court booking – ',
    'POS Sale – ',
    'Rental – ',
    'Open play – ',
)


def strip_tx_prefix(description):
    """Remove a leading type prefix from a legacy transaction description."""
    if not description:
        return description
    for prefix in TX_PREFIXES:
        if description.startswith(prefix):
            return description[len(prefix):]
    return description
