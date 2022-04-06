# -*- coding: utf-8 -*-
"""
Decorators to help write tango Devices
"""
__all__=["attribute","command","Command","SCPI_Instrument"]
import re
from asteval import Interpreter
from dataclasses import dataclass

import tango
import tango.server as server
import docstring_parser

from .funcs import sfmt, sbool

interp=Interpreter(usersyms=tango.__dict__,use_numpy=True)
range_pat=re.compile(r'range\s*\((?P<low>[^\,]+)\,(?P<high>[^\)]+)\)', flags=re.IGNORECASE)
warn_pat=re.compile(r'warn\s*\((?P<low>[^\,]+)\,(?P<high>[^\)]+)\)', flags=re.IGNORECASE)
alarm_pat=re.compile(r'alarm\s*\((?P<low>[^\,]+)\,(?P<high>[^\)]+)\)', flags=re.IGNORECASE)
return_pat=re.compile(r'((?P<label>.*)\s+in\s+(?P<unit>.*))|(?P<label2>.*)')

def attribute(f, **kargs):
    """Produces a tnago controls Device attribute using information from a docstring.
    
    This supplements the tango.server.attribute decorator by filling in as much detail
    as it can from the docstring in order to make this more pythonic.    
    Expect a docstring of the format::
        
    attribute doc string.
    
    Long descriptions
    Range (low,high)
    Warn (low,high)
    Alarm (low,high)
    
    Returns:
        dtype: Label in units.
    """
    dp=docstring_parser.parse(f.__doc__)
    annotations=f.__annotations__
    if dp.short_description:
        kargs.setdefault("doc",dp.short_description)
    if "return" in annotations:
        kargs.setdefault("dtype",annotations["return"])
    if dp.returns:
        kargs.setdefault("dtype",interp.eval(dp.returns.type_name))
        if match:=return_pat.search(dp.returns.description):
            dct=dict(match.groupdict())
            if dct["label"] is None:
                dct["label"]=dct["label2"]
            if dct["unit"] is not None:
                kargs.setdefault("unit",dct["unit"])
                kargs.setdefault("standard_unit",dct["unit"])
                kargs.setdefault("display_unit",dct["unit"])
            kargs.setdefault("label",dct["label"])
            
    if dp.long_description:
        for line in dp.long_description.split("\n"):
            line=line.strip()
            if match:=range_pat.search(line):
                low=interp.eval(match.groupdict()["low"])
                high=interp.eval(match.groupdict()["high"])
                kargs.setdefault("min_value",low)
                kargs.setdefault("max_value",high)
            if match:=warn_pat.search(line):
                low=interp.eval(match.groupdict()["low"])
                high=interp.eval(match.groupdict()["high"])
                kargs.setdefault("min_warning",low)
                kargs.setdefault("max_warning",high)
            if match:=alarm_pat.search(line):
                low=interp.eval(match.groupdict()["low"])
                high=interp.eval(match.groupdict()["high"])
                kargs.setdefault("min_alarm",low)
                kargs.setdefault("max_alarm",high)
                
    return server.attribute(f,**kargs)

def pipe(f, **kargs):
    """Produces a tnago controls Device pipe using information from a docstring.
    
    This supplements the tango.server.pipe decorator by filling in as much detail
    as it can from the docstring in order to make this more pythonic.    
    Expect a docstring of the format::
        
    pipe doc string.
       
    Returns:
        dtype: Label
    """
    dp=docstring_parser.parse(f.__doc__)
    if dp.short_description:
        kargs.setdefault("doc",dp.short_description)
    if dp.returns:
        if match:=return_pat.search(dp.returns.description):
            dct=dict(match.groupdict())
            if dct["label"] is None:
                dct["label"]=dct["label2"]
            kargs.setdefault("label",dct["label"])
    return server.pipe(f,**kargs)

def command(f, dtype_in=None,
            dformat_in=None,
            doc_in='',
            dtype_out=None,
            dformat_out=None,
            doc_out='',
            display_level=None,
            polling_period=None,
            green_mode=None):
    """Produces a tango.controls Device command using information from the docstring."""
    dp=docstring_parser.parse(f.__doc__)
    if dp.returns:
        doc_out=dp.returns.description
        dtype_out=dp.returns.type_name
    else:
        doc_out=doc_out if doc_out else "This command does not return any value."
    if len(dp.params)>0:
        param=dp.params[0]
        doc_in=param.description
        dtype_in=param.type_name
    else:
        doc_in = doc_in if doc_in else dp.short_description+"\nThis command takes no parameters."
    return server.command(f,
                          dtype_in=dtype_in,
                          dformat_in=dformat_in,
                          doc_in=doc_in,
                          dtype_out=dtype_out,
                          dformat_out=dformat_out,
                          doc_out=doc_out,
                          display_level=display_level,
                          polling_period=polling_period,
                          green_mode=green_mode)

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
    
    def __init__(self,*args,**kargs):
        super().__init__()
        if self.reader is None:
            if issubclass(self.dtype,bool):
                self.reader=sbool
            else:
                self.reader=self.dtype


def SCPI_Instrument(cls):
    
    """Another attempt to add attributes to a class based on a lookup table."""
    
    for item in getattr(cls,"scpi_attrs",[]):
        _process_one(cls, item)
    return server.DeviceMeta(cls.__name__, (cls,), {})

        
def _process_one(cls,item,cmd=""):
    if isinstance(item, list):
        for sub_item in item:
            _process_one(cls,sub_item,cmd)
    elif isinstance(item, dict):
        for key,sub_item in item.items():
            _process_one(cls, sub_item,f"{cmd}:{key}")
    elif isinstance(item,Command):
        access=None
        if item.read:
            def f_read(self):
                assert False, item.reader
                return item.reader(self.protocol.query(f"{cmd}?"))
            setattr(cls,f"read_{item.name}",f_read)
            access=tango.AttrWriteType.READ
            fget=f"read_{item.name}"
        else:
            fget=None
        if item.write:
            def f_write(self, value):
                self.protocol.write(f"{cmd} {sfmt(value)}")
            setattr(cls,f"write_{item.name}",f_write)
            access=tango.AttrWriteType.READ_WRITE if item.read else tango.AttrWriteType.WRITE
            fset=f"write_{item.name}"
        else:
            fset=None
        if access is None:
            return
        attr=server.attribute(fget=fget, fset=fset,label=item.label, doc=item.doc, dtype=item.dtype, unit=item.unit)
        setattr(cls,item.name,attr)
        #Add also to the TangoClassClass

            
    else:
        raise TypeError("Error defining scpi attributes with {item}")

