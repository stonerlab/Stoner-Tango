# -*- coding: utf-8 -*-
"""
Provides a Base Class for SCPI instruments.
"""

from pprint import pformat
import sys

import tango
from tango.server import device_property, Device

from stoner_tango.instr.base.transport import GPIBTransport
from stoner_tango.instr.base.protocol import SCPIProtocol
from stoner_tango.util.decorators import command, attribute, pipe, SCPI_Instrument
from stoner_tango.instr.exceptions import CommandError


class BaseDevice(Device):

    """Very Base class of the stoner_tango Deivce Server classes."""


class VISAInstrument(BaseDevice):

    """A Device class that represent a basic VISA instrument that can be communicated with over a VISA comms channel."""

    Resource = device_property(str, doc="VISA Resource name",
                           default_value="GPIB0::10::INSTR",
                           update_db = True)
    Sleep = device_property(float, doc="Wait time after sending commands",
                            default_value=0.1,
                            update_db=True)

    def __init__(self, *args, **kargs):
        """Construct the device server process."""
        super().__init__(*args)
        self.transport=GPIBTransport(self, name=self.Resource, sleep=self.Sleep)
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


    #### Basic comms commands for interacting with the instrument, Mainly for debugging.

    @command
    def Read(self):
        """Read data from instrument using the proptocol and transport.

        Returns:
            str: Instrument Response
        """
        return self.protocol.read()

    @command
    def Write(self,data):
        """Weite data to instrument using the protocol and transport.

        Args:
            data (str):
                Instrument Command

        Returns:
            int: Bytes sent to instrument.
        """
        return self.protocol.write(data)

    @command
    def Query(self, data):
        """Do a write-read cycle with the instrument using protocol and transport.

        Args:
            data (str):
                Instrument Command

        Returns:
            str: Instrument Response
        """
        self.protocol.write(data)
        return self.protocol.read()

@SCPI_Instrument
class IEEE488_2(VISAInstrument):

    """A base class for IEEE488.2 Compliant instruments."""


    @attribute
    def getScpiAttrs(self):
        """Get the tree of attributes generated from SCPI commands.

        Returns:
            str: SCPI_Attributes"""
        scpi_attrs=[]
        for cls in self.__mro__:
            scpi_attrs.extend(cls.__dict__.get("scpi_attrs",[]))
        return pformat(scpi_attrs)

    @attribute
    def getScpiCmds(self):
        """Get th dictionary of SCPI Commands implemented as attributes.

        Returns:
            str: SCPI_Attributes"""
        scpi_attrs={}
        for cls in self.__mro__:
            scpi_attrs.update(cls.__dict__.get("_scpi_cmds",{}))
        return pformat(scpi_attrs)

    @attribute
    def stb(self):
        """Get the Status Byte.

        Returns:
            int: Status Byte
        """
        if hasattr(self.transport,"stb"):
            return self.transport.stb
        return int(self.protocol.query("*STB?"))

    #### Implement IEEE488.2 Commands

    def Reset_posthook(self,value):
        """Clean up the status after reset."""
        stb=self.__read_stb_wrapper__(self.stb)
        if (stb&4)==0 and self.state==tango.DevState.ALARM:
            self.state=tango.DevState.ON
        return value




@SCPI_Instrument
class SCPI(IEEE488_2):

    """Further wraps the IEEE488.2 Instrument with a SCPI proptocol handler."""

    def __init__(self,*args, **kargs):
        """Construct the SCPI instrument.
        """
        super().__init__(*args)
        self.protocol = SCPIProtocol(self.transport)

    @pipe
    def NextError(self):
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
        print(f"SCPI Error: {error}", file=self.log_debug)
        return "Error",{"code":err_code,"message":err_msg}


if __name__=="__main__":
    SCPI.run_server()
