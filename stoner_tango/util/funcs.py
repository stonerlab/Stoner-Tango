# -*- coding: utf-8 -*-
"""
Extra utility functions
"""

__all__=["sbool","sfmt"]

from typing import Any
def sfmt(value:Any)->str:
    """Fomat the value depending on the type."""
    if isinstance(value,bool):
        return "ON" if value else "OFF"
    if isinstance(value,float):
        return f"{value:.6f}"
    if isinstance(value,str):
        return f'"{value}"'
    return f"{value}"

def sbool(value:Any)->bool:
    """Convert a value to a boolean."""
    value=str(value).lower().strip()
    return value in ["1","yes","on","true","t","y"]
