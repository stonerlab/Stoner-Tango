# -*- coding: utf-8 -*-
"""
Instrument Related Exceptions
"""

class CommandError(ValueError):
    
    """Triggered by an instrument failing to understand a command instruction."""
    
class NotConnectedError(IOError):
    
    """Raised when trying to communicate to a non-connected instrument."""
    
class NoDataError(ValueError):
    
    """There was no data to be read."""
    
class NoSuchInstrumentError(KeyError):
    
    """Raise for a non-existent instrument."""
