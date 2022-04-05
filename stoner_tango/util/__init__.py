__all__=["decorators","sfmt","sbool","Command"]
import sys
from typing import Any
from dataclasses import dataclass, field, make_dataclass

from tango.utils import TO_TANGO_TYPE

from . import decorators

FROM_TANGO_TYPE={v:k for k,v in TO_TANGO_TYPE.items()}

__module__=sys.modules[__name__]

def convert(arg):
    """Try to convert the argument to/from a tango type."""
    if arg in TO_TANGO_TYPE:
        return TO_TANGO_TYPE[arg]
    if arg in FROM_TANGO_TYPE:
        return FROM_TANGO_TYPE[arg]
    raise TypeError(f"Do not know how to convert type {arg}")
    
def build_class(pipe_arg):
    """Take the return data type if a pipe argument and convert it to a Python class."""
    name,definition=pipe_arg
    fields=[]
    data={}
    # Build a data dictionary and fields list
    if isinstance(definition,list): #Long format
        for fld in definition:
            data[fld["name"]]=fld["value"]
            fields.append((fld["name"],convert(fld["dtype"])))
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

@dataclass
class Command:
    
    name:str
    dtype:type
    doc:str=""
    label:str=""
    unit:str=""
    read:bool=True
    write:bool=True
    reader:callable=None
    
    def __inti__(self,*args,**kargs):
        super().__init__(*args, **kargs)
        if self.reader is None:
            if issubclass(self.dtype,bool):
                self.reader=sbool
            else:
                self.reader=self.dtype
