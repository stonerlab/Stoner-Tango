# -*- coding: utf-8 -*-
"""
Decorators to help write tango Devices
"""
__all__=["attribute","command","Command","SCPI_Instrument"]
from dataclasses import dataclass, fields
import enum
from inspect import getsourcefile
import pathlib
from pprint import pprint
import re
from typing import Optional, Tuple, List
import yaml

from asteval import Interpreter
import docstring_parser
import tango
import tango.server as server

from .funcs import sfmt, sbool

interp=Interpreter(usersyms=tango.__dict__,use_numpy=True)
range_pat=re.compile(r'range\s*\((?P<low>[^\,]+)\,(?P<high>[^\)]+)\)', flags=re.IGNORECASE)
warn_pat=re.compile(r'warn\s*\((?P<low>[^\,]+)\,(?P<high>[^\)]+)\)', flags=re.IGNORECASE)
alarm_pat=re.compile(r'alarm\s*\((?P<low>[^\,]+)\,(?P<high>[^\)]+)\)', flags=re.IGNORECASE)
return_pat=re.compile(r'((?P<label>.*)\s+in\s+(?P<unit>.*))|(?P<label2>.*)')

### Replacement decorators for tango.server

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

##### Machinery for the SCPI_Insastrument decorator

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
    range:Optional[Tuple[float,float]]=None
    alarm:Optional[Tuple[float,float]]=None
    warn:Optional[Tuple[float,float]]=None
    enum_labels:Optional[List[str]]=None

    def __post_init__(self):
        """Set the reader function  properly to handle scpi booleans."""
        if self.reader is None:
            if issubclass(self.dtype,bool):
                self.reader=sbool
            else:
                self.reader=self.dtype
        if issubclass(self.dtype,enum.Enum):
            self.enum_labels=list(self.dtype.__members__.keys())
            self.dtype=tango.DevEnum


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
        out["dtype"]=out["dtype"].__name__
        out["reader"]=out["reader"].__name__
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
            if name in["dtype","reader"]:
                new_dct[name]=interp.eval(dct[name])
            else:
                new_dct[name]=dct[name]
        return cls(**new_dct)


def Command_representer(dumper, data):
    """Makes a representation for :py:class:`Command` to enable dumping to a yaml file."""
    return dumper.represent_mapping('!Command', data.to_dict().items(), False)

def Command_constructor(loader, node):
    """Reconstruct a :py:class:`Command` instance from a yaml loader node."""
    mapping = loader.construct_mapping(node)
    return Command.from_dict(mapping,{"sbool":sbool})

def Enum_representer(dumper, data):
    """Makes a representation for :py:class:`Command` to enable dumping to a yaml file."""
    vals={}
    for name in data.__members__:
        vals[name]=getattr(data,name).value
    return dumper.represent_mapping('!ENUM', {"name":data.__name__,"values":vals}, False)

def Enum_constructor(loader, node):
    """Reconstruct a :py:class:`Command` instance from a yaml loader node."""
    mapping = loader.construct_mapping(node)
    return enum.Enum(mapping["name"], mapping["values"].items())

yaml.add_representer(Command,Command_representer)
yaml.add_constructor('!Command', Command_constructor)
yaml.add_representer(enum.EnumMeta,Enum_representer)
yaml.add_constructor('!ENUM', Enum_constructor)

def SCPI_Instrument(cls):

    """Construct a set of tango attributes to map to SCPI commands based on infromation in the decorated class.

    This decorator expects to either find an attribute called *scpi_attrs* in the class definition, or to load
    a similar data structure from a YAML file with the same name as class and .yaml extension that lives in the same
    directory as the fiule containing the class.

    The scpi_attrs attribute is a recursive list and dictionary structure as follows:

        scpi_attrs=[
            {"ROOT":[
                {"BRANCH":[
                    {"TWIG1":Command(name='attr_nme',
                                     dtype = python_type,
                                     label = "Short name",
                                     unit = 'Units for display",
                                     read = True|Fale,
                                     write = True|False,
                                     doc= 'Longer documentation string')},
                    {"TWIG2":[ .... ]}
                    ]},
                {"BRANCH2":[ ... ]},
                ]},
            {"ROOT2": [....]}
            ]

    The YAML file has the equivalent structure, wth the Command class be represented with a !Command tag.

    The decorator will create read_{attr-name} and write_{attr-name} methods that will send the relevant SCPI strings to the
    instrument and collect the replies, format them using the *reader* entry to convert them to the correct python data type.

    It then also creates a tango attribute of the same name that uses these read/write methods to make the data available over the
    tango Device api. The access mode is determined from the read & write fields of Command (which should reflect whether there is a
     matching SCPI ? query). The *name* and *dtype* fields of Command are mandetory, default values are prpvided for other fields.

    Internally the decorator is doing some slightly undocumented things with the tango.server.DataMeta to ensure this actually works!
    """

    clspth=pathlib.Path(getsourcefile(cls.__mro__[0])).parent # This is horrible and due to how tango.server.Device works

    clsyaml=clspth/f"{cls.__name__}.yaml"

    if not hasattr(cls,"scpi_attrs") and clsyaml.exists:
        scpi_attrs=yaml.load(clsyaml.read_text(),yaml.FullLoader)
        setattr(cls,"scpi_attrs", scpi_attrs)
    else:
        scpi_attrs=getattr(cls,"scpi_attrs",[])

    for item in scpi_attrs:
        _process_one(cls, item)
    return server.DeviceMeta(cls.__name__, (cls,), {})


def _process_one(cls,item,cmd=""):
    """Recursive function to be the machinery for the SCPI_Instrument decorator.

    Args:
        cls (tango.server.Decice class):
            The tango.server.Device subclass that we are decorating.
        item (list|dict|Command):
            The current bit of the scpi_attr being processed.
        cmd (str):
            The current SCPI command path as a string.

    Raises:
        TypeError:
            If item is not a list, dict, or Command instance.

    Modifies:
        cls:
            This will potentially add new attributes to the class being decorated.
            It's not very careful not to stomp on things - user beware!
    """
    if isinstance(item, list):
        for sub_item in item:
            _process_one(cls,sub_item,cmd)
    elif isinstance(item, dict):
        for key,sub_item in item.items():
            _process_one(cls, sub_item,f"{cmd}:{key}")
    elif isinstance(item,Command): # Do the actualy construction of the attribute
        access=None
        if item.read: # Patch in a suitable read function and make a not of its name
            def f_read(self):
                return item.reader(self.protocol.query(f"{cmd}?"))
            setattr(cls,f"read_{item.name}",f_read)
            access=tango.AttrWriteType.READ
            fget=f"read_{item.name}"
        else:
            fget=None
        if item.write: # PAtch in a suitable
            def f_write(self, value):
                self.protocol.write(f"{cmd} {sfmt(value)}")
            setattr(cls,f"write_{item.name}",f_write)
            access=tango.AttrWriteType.READ_WRITE if item.read else tango.AttrWriteType.WRITE
            fset=f"write_{item.name}"
        else:
            fset=None
        if access is None: # Really we should never get here - perhaps this should be an Exception!
            return
        # Build the arguments for the tango.server.attribute call
        ### TODO need to handle enum types somehowdum
        args={"fget":fget, "fset":fset, "label":item.label,"doc":item.doc, "dtype":item.dtype,"unit":item.unit,"access":access}
        if item.range is not None:
            if isinstance(item.range,str):
                item.range=interp.eval(item.range)
            args["min_value"],args["max_value"]=item.range
        if item.alarm is not None:
            if isinstance(item.alarm,str):
                item.alarm=interp.eval(item.alarm)
            args["min_alarm"],args["max_alarm"]=item.alarm
        if item.warn is not None:
            if isinstance(item.warn,str):
                item.warn=interp.eval(item.warn)
            args["min_warning"],args["max_warning"]=item.warn
        if item.dtype==tango.DevEnum and not isinstance(item.enum_labels, list):
            raise TypeError("Must specify enum_labels if the dtype is an enum!")
        if item.dtype==tango.DevEnum:
            args["enum_labels"]=item.enum_labels
        attr=server.attribute(**args)
        setattr(cls,item.name,attr)
    else:
        raise TypeError("Error defining scpi attributes with {item}")

