# -*- coding: utf-8 -*-
"""
Implementation of a dataclass that represents an attribute to map to a scpi command.
"""
__all__ = ["Command"]

from collections.abc import Iterable
from dataclasses import dataclass, fields
import enum
from typing import Union, Optional, Tuple, List
import yaml

from asteval import Interpreter
import numpy as np
import tango
from tango import server

from .funcs import sfmt, sbool

interp=Interpreter(usersyms=tango.__dict__,use_numpy=True)
interp.symtable["Empty"]=lambda x:""

@dataclass
class ListParameter:

    """Holds the information to configutr s tango attribute to deal with spectrum and image types."""

    name:str
    dtype:Union[type,enum.Enum]
    dims:int=1
    max_dim_x:int=2000
    max_dim_y:int=1
    delimiter:str=","

    def __post_init__(self):
        """Ensure consistency of dimensions."""
        if self.min_dim_x*self.min_dim_y<=1:
            raise ValueError("Cannot have a spectrum or image attrivute that is scalar!")
        if not 1<=self.dims<=2:
            raise ValueError("Only 1D or 2D datasets can be specified!")
        if self.dims==1 and self.max_dim_y>1:
            raise ValueError("Cannot have a spectrum with y dimension size set!")


    def to_dict(self):
        """Make a dictionary out of the fields of this class.

        This method is primarily useful for serialising instances of this class.
        Mostly the fields are just interpreted as is, but the dype and reader fields
        are simply given as the string names.

        The :py:meth:`ListParameter.from_dict` is the inverse of this method.

        Returns:
            dict: The ListParameter as a dictionary.
        """
        out={}
        for f in fields(self):
            out[f.name]=getattr(self,f.name)
        for k in out:
            if callable(out[k]):
                out[k]=k.__name__
        return out

    @classmethod
    def from_dict(cls, dct, symbols):
        """Build a class instance from a dictionary.

        Args:
            dct (dict):
                Dictionary containing the field data.
            symbols (dict):
                Additional symbols to use when reconstructing the dtype and reader fields.

        Returns:
            Command:
                A new instance of this class.
        """
        interp.symtable.update(symbols)
        fieldnames=set([f.name for f in fields(cls)])
        names=set(list(dct.keys()))
        new_dct={}
        for name in fieldnames&names:
            if name in["dtype"] and isinstance(dct[name],str):
                new_dct[name]=interp.eval(dct[name])
            else:
                new_dct[name]=dct[name]
        return cls(**new_dct)

    def adapt_args(self, args):
        """Adjust the tango.server.attribute arguments to deal wqith spectrum and image dtypes.

        Args:
            args (dict):
                The keywords for the attribute creation so far.

        Returns:
            dict: Modified args

        Warning:
            The parameter args is also modified by this method in place!
        """
        args["dtype"]=[self.dtype,] if self.dims==1 else [[self.dtype,],]
        args["min_dim_x"]=self.min_dim_x
        args["min_dim_y"]=self.min_dim_y
        return args

@dataclass
class Command:

    name:str
    dtype:Union[type,enum.Enum, ListParameter]
    doc:str=""
    label:str=""
    unit:str=""
    read:bool=True
    write:bool=True
    reader:callable=None
    writer:callable=sfmt
    range:Optional[Tuple[float,float]]=None
    alarm:Optional[Tuple[float,float]]=None
    warn:Optional[Tuple[float,float]]=None
    enum_labels:Optional[List[str]]=None

    def __post_init__(self):
        """Set the reader function  properly to handle scpi booleans."""
        if self.reader is None:
            self.reader=self.default_reader
        if self.writer is None:
            self.writer=self.default_writer

    def to_dict(self):
        """Make a dictionary out of the fields of this class.

        This method is primarily useful for serialising instances of this class.
        Mostly the fields are just interpreted as is, but the dype and reader fields
        are simply given as the string names.

        The :py:meth:`Command.from_dict` is the inverse of this method.

        Returns:
            dict: The Command as a dictionary.
        """
        out={}
        for f in fields(self):
            out[f.name]=getattr(self,f.name)
        for k in out:
            if callable(out[k]):
                out[k]=k.__name__
        return out

    @classmethod
    def from_dict(cls, dct, symbols):
        """Build a class instance from a dictionary.

        Args:
            dct (dict):
                Dictionary containing the field data.
            symbols (dict):
                Additional symbols to use when reconstructing the dtype and reader fields.

        Returns:
            Command:
                A new instance of this class.
        """
        interp.symtable.update(symbols)
        fieldnames=set([f.name for f in fields(cls)])
        names=set(list(dct.keys()))
        new_dct={}
        for name in fieldnames&names:
            if name in["dtype","reader","writer"] and isinstance(dct[name],str):
                new_dct[name]=interp.eval(dct[name])
            else:
                new_dct[name]=dct[name]
        return cls(**new_dct)

    def __repr__(self):
        """Make a representation that deals with callable objects in fields."""
        out={}
        for f in fields(self):
            f=f.name
            value=getattr(self,f)
            if callable(value):
                value=value.__name__
            else:
                value=repr(value)
            out[f]=value
        values=",".join([f"{k}={v}" for k,v in out.items()])
        return f"Command({values})"

    def default_reader(self,value):
        """Default implementation to convert a string to value of correct type."""
        if isinstance(value,self.dtype): # Do nothing
            try:
                return interp(value)
            except NameError:
                return value
        if isinstance(self.dtype, type) and issubclass(self.dtype,bool): # Boolean values might ON/OFF
            value=str(value).lower().strip()
            return value in ["1","yes","on","true","t","y"]
        if isinstance(self.dtype, type) and issubclass(self.dtype,enum.Enum): # ENUM types need special handling
            return getattr(self.dtype,value).value
        if isinstance(self.dtype, ListParameter): # Spectrum and Image types are handled recursively
            return np.array([self.default_reader(v.strip()) for v in value.split(self.dtype.delimiter)])
        #Fallback for all other types is to assume the type itself handles the conversion
        return self.dtype(value)

    def default_writer(self, value):
        """Convert a value to a string."""
        if isinstance(self.dtype,ListParameter) and isinstance(value, Iterable) and not isinstance(value,str):
            return self.dtype.delimiter.join([self.default_writer(v) for v in value])
        if issubclass(self.dtype,enum.Enum):
            if isinstance(value,int):
                return self.dtype(value).name
            if isinstance(value,str):
                return self.dtype[value]
            raise ValueError(f"Cannot map {value} into {self.dtype}")
        if isinstance(value,bool):
            return "ON" if value else "OFF"
        if isinstance(value,float):
            return f"{value:.6g}"
        if isinstance(value,str):
            return f'"{value}"'
        if isinstance(value,enum.Enum):
            return value.name
        return f"{value}"





    def adapat_tango_server(self,cls,cmd):
        """Use the current Command instance to add a suitable attribute to a tango.server.Device.

        Args:
            cls (tango.server.Device):
                The tange Decice server to add the attribute to.
            cmd (str):
                The SCPI command string that this attribute corresponds to.
        """
        access=None # Used to work out the access mode of the attribute
        if self.read: # Patch in a suitable read function and make a note of its name
            def f_read(this):
                return self.reader(this.protocol.query(f"{cmd}?"))
            setattr(cls,f"read_{self.name}",f_read)
            access=tango.AttrWriteType.READ
            fget=f"read_{self.name}"
        else:
            fget=None

        if self.write: # Patch in a suitable read function and make a note of its name
            def f_write(this, value):
                this.protocol.write(f"{cmd} {self.writer(value)}")
            setattr(cls,f"write_{self.name}",f_write)
            access=tango.AttrWriteType.READ_WRITE if self.read else tango.AttrWriteType.WRITE
            fset=f"write_{self.name}"
        else:
            fset=None
        if access is None: raise ValueError("Attempting to set an attrbute that is neither readable nor writable is not sensible!")

        # Build the arguments for the tango.server.attribute call
        ### TODO need to handle list types somehowdum

        args={"fget":fget, "fset":fset, "label":self.label,"doc":self.doc, "dtype":self.dtype,"unit":self.unit,"access":access}

        # Sort out the ListParameter dtype
        if isinstance(self.dtype,ListParameter):
            args = self.dtype.adapt_args(args)

        if self.range is not None:
            if isinstance(self.range,str):
                self.range=interp.eval(self.range)
            args["min_value"],args["max_value"]=self.range
        if self.alarm is not None:
            if isinstance(self.alarm,str):
                self.alarm=interp.eval(self.alarm)
            args["min_alarm"],args["max_alarm"]=self.alarm
        if self.warn is not None:
            if isinstance(self.warn,str):
                self.warn=interp.eval(self.warn)
            args["min_warning"],args["max_warning"]=self.warn
        if self.dtype==tango.DevEnum and not isinstance(self.enum_labels, list):
            raise TypeError("Must specify enum_labels if the dtype is an enum!")
        if self.dtype==tango.DevEnum:
            args["enum_labels"]=self.enum_labels
        attr=server.attribute(**args)
        setattr(cls,self.name,attr)
        scpi_cmds=cls.__dict__.get("_scpi_cmds",{})
        scpi_cmds[cmd]=self
        setattr(cls,"_scpi_cmds", scpi_cmds)




#### Setup functions to serialise the data classes and the Enum type to and from yaml files.

def Command_representer(dumper, data):
    """Makes a representation for :py:class:`Command` to enable dumping to a yaml file."""
    return dumper.represent_mapping('!Command', data.to_dict().items(), False)

def ListParameter_representer(dumper, data):
    """Makes a representation for :py:class:`ListParameter` to enable dumping to a yaml file."""
    return dumper.represent_mapping('!ListParameter', data.to_dict().items(), False)

def Enum_representer(dumper, data):
    """Makes a representation for :py:class:`Command` to enable dumping to a yaml file."""
    vals={}
    for name in data.__members__:
        vals[name]=getattr(data,name).value
    return dumper.represent_mapping('!ENUM', {"name":data.__name__,"values":vals})

def Command_constructor(loader, node):
    """Reconstruct a :py:class:`Command` instance from a yaml loader node."""
    mapping = loader.construct_mapping(node)
    return Command.from_dict(mapping,{"sbool":sbool})

def ListParameter_constructor(loader, node):
    """Reconstruct a :py:class:`ListParameter` instance from a yaml loader node."""
    mapping = loader.construct_mapping(node)
    return ListParameter.from_dict(mapping,{"sbool":sbool})

def Enum_constructor(loader, node):
    """Reconstruct a :py:class:`Command` instance from a yaml loader node."""
    mapping = loader.construct_mapping(node)
    labels = list(loader.construct_mapping(node.value[1][1]).items())
    labels.sort(key=lambda x:x[1])
    return enum.Enum(mapping["name"], labels)

yaml.add_representer(Command,Command_representer)
yaml.add_constructor('!Command', Command_constructor)
yaml.add_representer(ListParameter,ListParameter_representer)
yaml.add_constructor('!ListParameter', ListParameter_constructor)
yaml.add_representer(enum.EnumMeta,Enum_representer)
yaml.add_constructor('!ENUM', Enum_constructor)
