# -*- coding: utf-8 -*-
"""
Implementation of a dataclass that represents an attribute to map to a scpi command.
"""
__all__ = ["AttributeItem"]

from collections.abc import Iterable
from dataclasses import dataclass, fields
import enum
from typing import Union, Optional, Tuple, List
import yaml

from asteval import Interpreter
import numpy as np
import tango
from tango import server

from . import funcs

interp=Interpreter(usersyms=tango.__dict__,use_numpy=True)
interp.symtable["Empty"]=lambda x:""
interp.symtable.update(funcs.__dict__)

BUILTIN_NAMES={}
for k,v in __builtins__.items():
    try:
        BUILTIN_NAMES[v]=k
    except TypeError:
        pass
    

@dataclass
class ListParameter:

    """Holds the information to configutr s tango attribute to deal with spectrum and image types."""

    name:str
    dtype:Union[type,enum.Enum]
    dims:int=1
    max_dim_x:int=2000
    max_dim_y:int=0
    delimiter:str=","

    def __post_init__(self):
        """Ensure consistency of dimensions."""
        if not 1<=self.dims<=2:
            raise ValueError("Only 1D or 2D datasets can be specified!")
        if self.dims==1 and (self.max_dim_x<2 or self.max_dim_y>0):
            raise ValueError("Cannot have a spectrum with y dimension size set or not x dimension set!")
        if self.dims==2 and self.max_dim_x*self.max_dim_y<=1:
            raise ValueError("Cannot have a image attrivute that is scalar!")
        self.__name__=self.name
            
    def __call__(self,value):
        """Make the ListParameter callable to do a type conversion using it's own dtype."""
        return self.dtype(value)

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
            AttributeItem:
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

    def adapt_args(self, args, suffix=""):
        """Adjust the tango.server.attribute arguments to deal wqith spectrum and image dtypes.

        Args:
            args (dict):
                The keywords for the attribute creation so far.
            suffix (str):
                Suffix to add to the dtype and dformat arguments e.g. _in or _out for writing tango.server.command 's'

        Returns:
            dict: Modified args

        Warning:
            The parameter args is also modified by this method in place!
        """
        if issubclass(self.dtype,enum.Enum):
            dtype=int
        else:
            dtype=self.dtype
        args[f"dtype{suffix}"]=dtype
        args[f"dformat{suffix}"]=tango.AttrDataFormat.SPECTRUM if self.dims==1 else tango.AttrDataFormat.IMAGE
        if suffix=="": #Attribute access has these parameters, commands appear not to have.
            args["max_dim_x"]=self.max_dim_x
            args["max_dim_y"]=self.max_dim_y
        return args

@dataclass
class AttributeItem:

    name:str
    dtype:Union[type,enum.Enum, ListParameter]
    doc:str=""
    label:str=""
    unit:str=""
    read:bool=True
    write:bool=True
    reader:callable=None
    writer:callable=None
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

        The :py:meth:`AttributeItem.from_dict` is the inverse of this method.

        Returns:
            dict: The AttributeItem as a dictionary.
        """
        out={}
        for f in fields(self):
            out[f.name]=getattr(self,f.name)
        for k in out:
            if callable(out[k]):
                try:
                    out[k]=k.__name__
                except AttributeError:
                    out[k]=BUILTIN_NAMES.get(out[k],None)
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
            AttributeItem:
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
        return f"AttributeItem({values})"

    def default_reader(self,value,dtype=None):
        """Default implementation to convert a string to value of correct type."""
        if dtype is None:
            dtype=self.dtype
        value=value.strip("\"\'")
        if isinstance(dtype,type) and isinstance(value,dtype): # Do nothing
            return value
        if isinstance(dtype, type) and issubclass(dtype,bool): # Boolean values might ON/OFF
            value=str(value).lower().strip()
            return value in ["1","yes","on","true","t","y"]
        if isinstance(dtype, type) and issubclass(dtype,enum.Enum): # ENUM types need special handling
            return getattr(dtype,value).value
        if isinstance(dtype, ListParameter): # Spectrum and Image types are handled recursively
            if issubclass(dtype.dtype,enum.Enum): #Enums get converted to ints
                return np.array([dtype.dtype[v].value for v in value.split(self.dtype.delimiter)])
            if not self.dtype.delimiter:
                return np.array([self.default_reader(v.strip(),dtype=self.dtype.dtype) for v in value])
            return np.array([self.default_reader(v.strip(),dtype=self.dtype.dtype) for v in value.split(self.dtype.delimiter)])
        #Fallback for all other types is to assume the type itself handles the conversion
        return dtype(value)

    def default_writer(self, value):
        """Convert a value to a string."""
        if isinstance(self.dtype,ListParameter) and isinstance(value, Iterable) and not isinstance(value,str):
            if issubclass(self.dtype.dtype,enum.Enum): # special adaptation for Enum's
                ret= self.dtype.delimiter.join([self.dtype.dtype(v).name for v in value])
                return ret                
            return self.dtype.delimiter.join([self.default_writer(v) for v in value])
        if isinstance(self.dtype, type) and issubclass(self.dtype,enum.Enum):
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
        """Use the current AttributeItem instance to add a suitable attribute to a tango.server.Device.

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

@dataclass
class CommandItem:

    name:str
    dtype_in:Union[type,enum.Enum, ListParameter, None]
    dtype_out:Union[type,enum.Enum, ListParameter, None]
    doc_in:str=""
    doc_out:str=""
    doc:str=""
    reader:callable=None
    writer:callable=None
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

        The :py:meth:`AttributeItem.from_dict` is the inverse of this method.

        Returns:
            dict: The AttributeItem as a dictionary.
        """
        out={}
        for f in fields(self):
            out[f.name]=getattr(self,f.name)
        for k in out:
            if callable(out[k]):
                try:
                    out[k]=k.__name__
                except AttributeError:
                    out[k]=BUILTIN_NAMES.get(out[k],None)
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
            AttributeItem:
                A new instance of this class.
        """
        interp.symtable.update(symbols)
        fieldnames=set([f.name for f in fields(cls)])
        names=set(list(dct.keys()))
        new_dct={}
        for name in fieldnames&names:
            if name in["dtype_in","dtype_out","reader","writer"] and isinstance(dct[name],str):
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
        return f"CommandItem({values})"

    def default_reader(self,value,dtype=None):
        """Default implementation to convert a string to value of correct type."""
        if dtype is None:
            dtype=self.dtype_out
        value=value.strip("\"\'")
        if isinstance(dtype,type) and isinstance(value,dtype): # Do nothing
            return value
        if isinstance(dtype, type) and issubclass(dtype,bool): # Boolean values might ON/OFF
            value=str(value).lower().strip()
            return value in ["1","yes","on","true","t","y"]
        if isinstance(dtype, type) and issubclass(dtype,enum.Enum): # ENUM types need special handling
            return getattr(dtype,value).value
        if isinstance(dtype, ListParameter): # Spectrum and Image types are handled recursively
            if issubclass(dtype.dtype,enum.Enum): #Enums get converted to ints
                return np.array([dtype.dtype[v].value for v in value.split(self.dtype.delimiter)])
            if not self.dtype.delimiter:
                return np.array([self.default_reader(v.strip(),dtype=self.dtype.dtype) for v in value])
            return np.array([self.default_reader(v.strip(),dtype=self.dtype.dtype) for v in value.split(self.dtype.delimiter)])
        #Fallback for all other types is to assume the type itself handles the conversion
        return dtype(value)

    def default_writer(self, value):
        """Convert a value to a string."""
        if isinstance(self.dtype_in,ListParameter) and isinstance(value, Iterable) and not isinstance(value,str):
            if issubclass(self.dtype_in.dtype,enum.Enum): # special adaptation for Enum's
                ret= self.dtype_in.delimiter.join([self.dtype_in.dtype(v).name for v in value])
                return ret                
            return self.dtype_in.delimiter.join([self.default_writer(v) for v in value])
        if isinstance(self.dtype_in, type) and issubclass(self.dtype_in,enum.Enum):
            if isinstance(value,int):
                return self.dtype_in(value).name
            if isinstance(value,str):
                return self.dtype_in[value]
            raise ValueError(f"Cannot map {value} into {self.dtype_in}")
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
        """Use the current CommandItem instance to add a suitable attribute to a tango.server.Device.

        Args:
            cls (tango.server.Device):
                The tange Decice server to add the attribute to.
            cmd (str):
                The SCPI command string that this attribute corresponds to.
        """
        access=None # Used to work out the access mode of the attribute
        def execute_cmd(this,parameter=None):
            if self.dtype_in is not None and parameter is not None:
                parameter=self.writer(parameter)
            else:
                parameter=""
            if self.dtype_out is not None:
                return self.reader(this.protocol.query(f"{cmd}? {parameter}"))
            return this.protocol.write(f"{cmd} {parameter}")
        execute_cmd.__name__=f"{self.name}"
        execute_cmd.__doc__=f"{cmd}\n{self.doc}\n\nArg:\n\t{self.doc_in}\n\nReturns\n\t{self.doc_out}\n"
        setattr(cls,f"__execute_{self.name}",execute_cmd)
        

        # Build the arguments for the tango.server.attribute call

        args={"dtype_in":self.dtype_in,"dtype_out":self.dtype_out,"doc_in":self.doc_in, "doc_in":self.doc_out}
        if isinstance(self.dtype_in, ListParameter):
            args=self.dtype_in.adapt_args(args,"_in")
        if isinstance(self.dtype_out, ListParameter):
            args=self.dtype_in.adapt_args(args,"_out")

        new_cmd=server.command(execute_cmd, **args)
        setattr(cls,self.name,new_cmd)
        scpi_cmds=cls.__dict__.get("_scpi_cmds",{})
        scpi_cmds[cmd]=self
        setattr(cls,"_scpi_cmds", scpi_cmds)



#### Setup functions to serialise the data classes and the Enum type to and from yaml files.

def AttributeItem_representer(dumper, data):
    """Makes a representation for :py:class:`AttributeItem` to enable dumping to a yaml file."""
    return dumper.represent_mapping('!Attribute', data.to_dict().items(), False)

def CommandItem_representer(dumper, data):
    """Makes a representation for :py:class:`AttributeItem` to enable dumping to a yaml file."""
    return dumper.represent_mapping('!Command', data.to_dict().items(), False)

def ListParameter_representer(dumper, data):
    """Makes a representation for :py:class:`ListParameter` to enable dumping to a yaml file."""
    return dumper.represent_mapping('!ListParameter', data.to_dict().items(), False)

def Enum_representer(dumper, data):
    """Makes a representation for :py:class:`AttributeItem` to enable dumping to a yaml file."""
    vals={}
    for name in data.__members__:
        vals[name]=getattr(data,name).value
    return dumper.represent_mapping('!ENUM', {"name":data.__name__,"values":vals})

def AttributeItem_constructor(loader, node):
    """Reconstruct a :py:class:`AttributeItem` instance from a yaml loader node."""
    mapping = loader.construct_mapping(node)
    return AttributeItem.from_dict(mapping,{})

def CommandItem_constructor(loader, node):
    """Reconstruct a :py:class:`AttributeItem` instance from a yaml loader node."""
    mapping = loader.construct_mapping(node)
    return CommandItem.from_dict(mapping,{})

def ListParameter_constructor(loader, node):
    """Reconstruct a :py:class:`ListParameter` instance from a yaml loader node."""
    mapping = loader.construct_mapping(node)
    return ListParameter.from_dict(mapping,{})

def Enum_constructor(loader, node):
    """Reconstruct a :py:class:`AttributeItem` instance from a yaml loader node."""
    mapping = loader.construct_mapping(node)
    labels = list(loader.construct_mapping(node.value[1][1]).items())
    labels.sort(key=lambda x:x[1])
    return enum.Enum(mapping["name"], labels)

yaml.add_representer(AttributeItem,AttributeItem_representer)
yaml.add_constructor('!Attribute', AttributeItem_constructor)
yaml.add_representer(CommandItem,CommandItem_representer)
yaml.add_constructor('!Command', CommandItem_constructor)
yaml.add_representer(ListParameter,ListParameter_representer)
yaml.add_constructor('!ListParameter', ListParameter_constructor)
yaml.add_representer(enum.EnumMeta,Enum_representer)
yaml.add_constructor('!ENUM', Enum_constructor)
