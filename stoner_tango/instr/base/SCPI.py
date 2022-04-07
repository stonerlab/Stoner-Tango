# -*- coding: utf-8 -*-
"""
Provides a Base Class for SCPI instruments.
"""

from pprint import pformat

import tango
from tango.server import run
from tango.server import Device
from tango.server import device_property
from tango.attr_data import AttrData
from tango.utils import TO_TANGO_TYPE

from stoner_tango.instr.base.transport import GPIBTransport
from stoner_tango.instr.base.protocol import SCPIProtocol
from stoner_tango.util.decorators import command, attribute, pipe, SCPI_Instrument
from stoner_tango.util import Command, sfmt
from stoner_tango.instr.exceptions import CommandError

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
        self._debug = False

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


    @attribute
    def debug(self):
        """Anable debugging log of instrument transactions.

        Returns:
            bool: Debug On?
        """
        return self._debug

    @debug.write
    def debug(self, value):
        self._debug=bool(value)

    #### Implement IEEE488.2 Commands

    @command
    def reset(self):
        """Reset the instrument to defaults."""
        try:
            self.protocol.write("*RST")
        except CommandError:
            self.state=tango.DevState.ALARM
        else:
            self.state=tango.DevState.ON
            self.status="Instrument reset"

    @command
    def cls(self):
        """Issue a CLS command to clear register bits and error queue."""
        try:
            self.protocol.write("*CLS")
        except CommandError:
            self.state=tango.DevState.ALARM
        else:
            self.state=tango.DevState.ON
            self.status="Instrument cleared"

    @attribute
    def opc(self):
        """Set the operation complete bit or waits for the current operation to complete.

        Returns:
            bool: Operation Complete
        """
        self.state=tango.DevState.MOVING
        self.protocol.query("*OPC?")
        self.steate=tango.DevState.ON
        return True

    @opc.write
    def opc(self,set):
        if set:
            self.protocol.write("*OPC")


    @attribute
    def sre(self):
        """Set or read the service request enable mask.

        Returns:
            int:
                SRQ Enable
        """
        return  int(self.protocol.query("*SRE?"))

    @sre.write
    def sre(self,bits):
        bits=int(bits)
        self.protocol.write(f"*SRE {bits%256}")
        return bits%256

@SCPI_Instrument
class SCPI(IEEE488_2):

    """Further wraps the IEEE488.2 Instrument with a SCPI proptocol handler."""

    def __init__(self,*args, **kargs):
        """Construct the SCPI instrument.
        """
        super().__init__(*args)
        self.protocol = SCPIProtocol(self.transport)

    @tango.server.pipe
    def next_error(self):
        """Read the enxt werror message from the queue.

        Returns:
            Ruple[str, List[Dict]: Error Message
        """
        error=self.protocol.query("SYST:ERR:NEXT?")
        match=self.protocol.err_pat.match(error)
        if not match:
            print(f"Unrecognised error response {error}", file=self.log_debug)
            return "Error",{"code":0,"message":error}
        err_code=int(match.groupdict()["code"])
        err_msg=match.groupdict()["msg"]
        return "Error",{"code":err_code,"message":err_msg}

    @attribute
    def get_scpi_attrs(self):
        """Get a list of SCPI commands to be converted to attributes.

        Returns:
            str: SCPI_Attributes"""
        return pformat(getattr(self,"scpi_attrs",[]))


if __name__=="__main__":
    SCPI.run_server()
