# -*- coding: utf-8 -*-
"""
Extra utility functions
"""

__all__=["sfmt"]
import enum
from typing import Any, Union
import numpy as np

def sfmt(value:Any)->str:
    """Fomat the value depending on the type."""
    if isinstance(value,bool):
        return "ON" if value else "OFF"
    if isinstance(value,float):
        return f"{value:.6f}"
    if isinstance(value,str):
        return f'"{value}"'
    if isinstance(value,enum.Enum):
        return value.name
    return f"{value}"

def glue_and_quote(value):
    value="".join([f"{v:1d}" for v in value])
    return f'"{value}"'

def EnumQuoted(value):
    return f'"{value.name}"'

def WriteNegAsInf(value):
    if value<0:
        return "INF"
    return f"{value:d}"

def ReadLargeAsInf(value):
    res=float(value)
    if res>1E10:
        return -1
    return int(res)

def ExtractFloats(data:Union[str,bytes])->np.ndarray:
    """Try to extract a numpy array from a SCPI data string."""
    if len(data)>2 and data[:2]=="#0":
        if not isinstance(data, bytes):
            data=data.encode()
        return np.frombuffer(data,dtype=np.float32)
    return np.fromstring(data, dtype=np.float32,sep=",")