# -*- coding: utf-8 -*-
"""
Provides a Base Class for SCPI instruments.
"""

import tango
from tango.server import run
from tango.server import Device
from tango.server import device_property, pipe

from stoner_tango.instr.base.transport import GPIBTransport
from stoner_tango.instr.base.protocol import SCPIProtocol
from stoner_tango.util.decorators import command, attribute

class IEEE488_2(Device):
    
    """A base class for SCPI instruments."""
    
    name = device_property(str, doc="VISA Resource name", 
                           default_value="GPIB0::10::INSTR",
                           update_db = True)
    sleep = device_property(float, doc="Wait time after sending commands",
                            default_value=0.1,
                            update_db=True)
    
    def __init__(self, *args, **kargs):
        """Construct the device server process."""
        super().__init__(*args)
        self.transport=GPIBTransport(self, name=self.name, sleep=self.sleep)
        
    @property
    def state(self):
        return self.get_state()
    
    @state.setter
    def state(self,state):
        self.set_state(state)
        
    @property
    def status(self):
        return self.get_status()
    
    @status.setter
    def status(self,status):
        self.set_status(status)        
        
    #### IEEE488.2 standard queries
        
    @attribute
    def idn(self):
        """Return the instrument identity string.
        
        Returns:
            str:
                Instrument Identity.
        """
        return self.protocol.query("*IDN?")
    
        
    #### Implement IEEE488.2 Commands
    
    @command
    def resst(self):
        """Reset the instrument to defaults."""
        self.protocol.write("*RST")
        
    @command
    def cls(self):
        """Issue a CLS command to clear register bits and error queue."""
        self.protocol.write("*CLS")
        
    @command
    def opc(self, set=None):
        """Set the operation complete bit or waits for the current operation to complete.
        
        Args:
            set (bool):
                If true, set the OPC bit on completion, else do a query command.
        """
        if set:
            self.protocol.write("*OPC")
        else:
            self.state=tango.DevState.MOVING
            self.protocol.query("*OPC?")
            self.steate=tango.DevState.ON
            
    @command
    def sre(self, bits=None):
        """Set or read the service request enable mask.
        
        Args:
            bits (int):
                If not None, mask to set the service request enable with.
        
        Returns:
            int:
                Service request ebable mask.
        """
        if bits is not None and bits>=0:
            bits=int(bits)
            self.protocol.write(f"*SRE {bits%256}")
            return bits%256
        return  int(self.protocol.query("*SRE?"))
        
        
class SCPI(IEEE488_2):
    
    """Further wraps the IEEE488.2 Instrument with a SCPI proptocol handler."""
    
    def __init__(self,*args, **kargs):
        """Construct the SCPI instrument."""
        super().__init__(*args)
        self.protocol = SCPIProtocol(self.transport)
        
    @attribute
    def version(self):
        """Get the system version number.
        
        Returns:
            str:
                The version string.
        """
        return self.protocol.query("SYST:VERS?")
    
    @pipe
    def next_error(self):
        """Read the enxt werror message from the queue."""
        error=self.protocol.query("SYST:ERR:NEXT?")
        match=self.protocol.err_pat.match(error)
        if not match:
            print(f"Unrecognised error response {error}", file=self.log_debug)
            return "Error",{"code":0,"message":error}
        err_code=int(match.groupdict()["code"])
        err_msg=match.groupdict()["msg"]
        return "Error",{"code":err_code,"message":err_msg}
        
    
    

    
        
    
if __name__=="__main__":
    SCPI.run_server()