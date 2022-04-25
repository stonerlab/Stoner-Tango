# -*- coding: utf-8 -*-
"""A set of monkey patches to tango/ These are not intended to be used directly, but to run as
part of an import of stoner_tango."""
import dataclasses

import tango
from tango import server
from tango.utils import dir2

from .util import build_class

def is_tango_object(arg):
    """PAtched version of default tango.server.is_tango_object.

    Return tango data if the argument is a tango object,
    False otherwise.
    """
    classes = server.attribute, server.device_property, server.pipe
    if isinstance(arg, classes):
        return arg
    try:
        return arg.__tango_command__
    except AttributeError:
        return False

server.is_tango_object=is_tango_object

devprox_read_pipe=tango.device_proxy.__DeviceProxy__read_pipe
devprox_write_pipe=tango.device_proxy.__DeviceProxy__write_pipe

def new_read_pipe(self, pipe_name, extract_as=tango.ExtractAs.Numpy):
    """Replacement for DeviceProxy.read_pipe."""
    data =devprox_read_pipe(self, pipe_name, extract_as)
    return build_class(data)

def new_write_pipe(self, *args, **kwargs):
    """Patch in code to convet data classes to a pipe data structure in compact form."""
    for ix,arg in enumerate(args):
        if dataclasses.is_dataclass(arg):
            data=dataclasses.asdict(arg)
            name=arg.__class__.__name__
            args[ix]=(name,data)
    return devprox_write_pipe(self, *args, **kwargs)


def new_devproxy__dir__(self):
    """Return the attribute list including tango objects.

    Do not convert tango objects to lower case!"""
    extra_entries = set()
    # Add commands
    try:
        extra_entries.update(self.get_command_list())
    except Exception:
        pass
    # Add attributes
    try:
        extra_entries.update(self.get_attribute_list())
    except Exception:
        pass
    # Add pipes
    try:
        extra_entries.update(self.get_pipe_list())
    except Exception:
        pass
    # Merge with default dir implementation
    #extra_entries.update([x.lower() for x in extra_entries])
    entries = extra_entries.union(dir2(self))
    return sorted(entries)


# Do the patching
tango.DeviceProxy.read_pipe=new_read_pipe
tango.DeviceProxy.write_pipe=new_write_pipe
tango.DeviceProxy.__dir__=new_devproxy__dir__
