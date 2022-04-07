# -*- coding: utf-8 -*-
"""A set of monkey patches to tango/ These are not intended to be used directly, but to run as
part of an import of stoner_tango."""
import tango
from tango import server

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

def new_read_pipe(self, pipe_name, extract_as=tango.ExtractAs.Numpy):
    """Replacement for DeviceProxy.read_pipe."""
    data =devprox_read_pipe(self, pipe_name, extract_as)
    return build_class(data)
    
tango.DeviceProxy.read_pipe=new_read_pipe
