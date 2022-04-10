# -*- coding: utf-8 -*-
"""
Decorators to help write tango Devices
"""
__all__=["attribute","command","SCPI_Instrument"]
from inspect import getsourcefile
import pathlib
import re
import yaml

from asteval import Interpreter
import docstring_parser
import tango
import tango.server as server

from .command import AttributeItem, CommandItem
from .import command as st_commands

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
    """Produces a tango.controls Device command using information from the docstring.
    
    Uses the parameters from the doc string to determine the type and description of the input parameters and the
    return type and description for the output dtype and description.
    """
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


def SCPI_Instrument(cls):

    """Construct a set of tango attributes to map to SCPI commands based on infromation in the decorated class.

    This decorator expects to either find an attribute called *scpi_attrs* in the class definition, or to load
    a similar data structure from a YAML file with the same name as class and .yaml extension that lives in the same
    directory as the fiule containing the class.

    The scpi_attrs attribute is a recursive list and dictionary structure as follows:

        scpi_attrs=[
            {"ROOT":[
                {"BRANCH":[
                    {"TWIG1":AttributeItem(name='attr_nme',
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

    The YAML file has the equivalent structure, wth the AttributeItem class be represented with a !AttributeItem tag.

    The decorator will create read_{attr-name} and write_{attr-name} methods that will send the relevant SCPI strings to the
    instrument and collect the replies, format them using the *reader* entry to convert them to the correct python data type.

    It then also creates a tango attribute of the same name that uses these read/write methods to make the data available over the
    tango Device api. The access mode is determined from the read & write fields of AttributeItem (which should reflect whether there is a
     matching SCPI ? query). The *name* and *dtype* fields of AttributeItem are mandetory, default values are prpvided for other fields.

    Internally the decorator is doing some slightly undocumented things with the tango.server.DataMeta to ensure this actually works!
    """

    clspth=pathlib.Path(getsourcefile(cls.__mro__[0])).parent # This is horrible and due to how tango.server.Device works

    clsyaml=clspth/f"{cls.__name__}.yaml"
    
    st_commands._enum_types={} # C

    if "scpi_attrs" not in cls.__dict__ and clsyaml.exists:
        scpi_attrs=yaml.load(clsyaml.read_text(),yaml.FullLoader)
        defined=cls.__dict__.get("scpi_attrs",[])
        defined.extend(scpi_attrs)
        setattr(cls,"scpi_attrs", defined)
    else:
        scpi_attrs=getattr(cls,"scpi_attrs",[])
        
    # cls._scpi_attrs is a mapping between the class attribute (tango attribute/command) and the SCPI command implemented
    # for debuggin purposes!
    _scpi_attrs=getattr(cls,"_scpi_attrs",{})
    setattr(cls,'_scpi_attrs',_scpi_attrs)

    for item in scpi_attrs:
        _process_one(cls, item)
    return server.DeviceMeta(cls.__name__, cls.__mro__, {})


def _process_one(cls,item,cmd=""):
    """Recursive function to be the machinery for the SCPI_Instrument decorator.

    Args:
        cls (tango.server.Decice class):
            The tango.server.Device subclass that we are decorating.
        item (list|dict|AttributeItem):
            The current bit of the scpi_attr being processed.
        cmd (str):
            The current SCPI command path as a string.

    Raises:
        TypeError:
            If item is not a list, dict, or AttributeItem instance.

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
    elif isinstance(item,(AttributeItem, CommandItem)): # Do the actualy construction of the attribute
        item.adapat_tango_server(cls,cmd)
        cls._scpi_attrs[item.name]=cmd
    else:
        raise TypeError(f"Error defining scpi attributes with {item}")

