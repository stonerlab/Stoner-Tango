# -*- coding: utf-8 -*-
"""
Decorators to help write tango Devices
"""
__all__=["attribute","command","cmd","SCPI_attrs"]
from dataclasses import dataclass
import numpy as np

import tango.server as server
from tango.attr_data import AttrData
import docstring_parser

def attribute(f, **kargs):
    """Produces a tnago controls Device attribute using information from a docstring."""
    dp=docstring_parser.parse(f.__doc__)
    annotations=f.__annotations__
    if dp.short_description:
        kargs.setdefault("doc",dp.short_description)
    if dp.returns:
        kargs.setdefault("dtype",dp.returns.type_name)
    if "return" in annotations:
        kargs.setdefault(annotations["return"])
    return server.attribute(f,**kargs)


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
class cmd:

    cmd:str
    dtype:type
    read:bool=True
    write:bool=True
    descr:str=""
    range:tuple=(-np.inf,np.inf)
    label:str=""
    units:str=""

    def create_attr(self,obj,scpi_cmd):
        """Create and return a tango controls attribute from this data class."""
        if self.read:
            def fread(dev):
                return self.dtype(dev.protocol.query(f"{scpi_cmd}?"))
        else:
            fread=None
        if self.write:
            def fwrite(dev, value):
                dev.protocol.write(f"{scpi_cmd} {value}")
        else:
            fwrite=None

        attr=AttrData.from_dict({
            "name":self.cmd,
            "dtype":self.dtype,
            "fread":fread,
            "fwrite":fwrite,
            "label":self.label,
            "unit":self.units,
            "doc":self.desc,})
        obj.add_attrbute(attr,fread=fread,frwrite=fwrite)
