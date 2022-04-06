__all__=["decorators","fuuncs", "sfmt","sbool","Command"]
import sys
from typing import Any
from dataclasses import make_dataclass

from tango.utils import TO_TANGO_TYPE

from . import decorators
from.funcs import sfmt,sbool
from .decorators import Command

FROM_TANGO_TYPE={}
for k,v in TO_TANGO_TYPE.items():
    if not isinstance(k,str) and "tango" not in k.__class__.__module__:
        FROM_TANGO_TYPE[v]=k

__module__=sys.modules[__name__]

def convert(arg, to_tango=False):
    """Try to convert the argument to/from a tango type."""
    maps=TO_TANGO_TYPE,FROM_TANGO_TYPE if to_tango else FROM_TANGO_TYPE, TO_TANGO_TYPE
    for mapping in maps:
        if arg in mapping:
            return mapping[arg]
    raise TypeError(f"Do not know how to convert type {arg}")
    
def build_class(pipe_arg):
    """Take the return data type if a pipe argument and convert it to a Python class."""
    name,definition=pipe_arg
    fields=[]
    data={}
    # Build a data dictionary and fields list
    if isinstance(definition,list): #Long format
        for fld in definition:
            typ=convert(fld["dtype"])
            fields.append((fld["name"],typ))
            data[fld["name"]]=typ(fld["value"])
    elif isinstance(definition, dict): # Compact format
        for fld,value in definition.items():
            data[fld]=value
            fields.append((name,type(value)))
    cls=__module__.__dict__.get(name,None) # Try to class definition from this module
    if cls is None or not isinstance(cls,type): # Need to make a new class
        new_cls=make_dataclass(name, fields)
        if cls is None: # If we're not colliding names, then put class into this module
            __module__.__dict__[name]=new_cls
        cls=new_cls
    return cls(**data)
        

