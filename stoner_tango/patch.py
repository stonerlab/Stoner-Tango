# -*- coding: utf-8 -*-
"""A set of monkey patches to tango/ These are not intended to be used directly, but to run as
part of an import of stoner_tango."""
from tango import server

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