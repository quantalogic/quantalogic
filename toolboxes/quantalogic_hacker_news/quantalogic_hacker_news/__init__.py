from .tools import get_hn_item_details, get_hn_items, get_hn_user, search_hn

__all__ = [
    "get_hn_items",
    "get_hn_item_details",
    "get_hn_user",
    "search_hn",
    "get_tools"
]

def get_tools():
    """Return a list of tool functions for registration."""
    return [get_hn_items, get_hn_item_details, get_hn_user, search_hn]