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
from stoner_tango.util.decorators import command, attribute, cmd

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
    def reset(self):
        """Reset the instrument to defaults."""
        self.protocol.write("*RST")

    @command
    def cls(self):
        """Issue a CLS command to clear register bits and error queue."""
        self.protocol.write("*CLS")

    @attribute
    def opc(self):
        """Set the operation complete bit or waits for the current operation to complete.

        Args:
            set (bool):
                If true, set the OPC bit on completion, else do a query command.

        Returns:
            bool:
                Truie if operation complete
        """
        self.state=tango.DevState.MOVING
        self.protocol.query("*OPC?")
        self.steate=tango.DevState.ON

    @opc.write
    def opc(self,set):
        if set:
            self.protocol.write("*OPC")


    @attribute
    def sre(self):
        """Set or read the service request enable mask.

        Args:
            bits (int):
                If not None, mask to set the service request enable with.

        Returns:
            int:
                Service request ebable mask.
        """
        return  int(self.protocol.query("*SRE?"))

    @sre.write
    def sre(self,bits):
        bits=int(bits)
        self.protocol.write(f"*SRE {bits%256}")
        return bits%256


class SCPI(IEEE488_2):

    """Further wraps the IEEE488.2 Instrument with a SCPI proptocol handler."""

    def __init__(self,*args, **kargs):
        """Construct the SCPI instrument.

        This will look for an attribute scpi_attrs which is a mapping between the SCPI commands and tango attributes.

        scpi_attrs =
            [{"ROOT":[
                {"STEM":[
                    {"LEAF":cmd(....)},
                    cmd(...)]},
                {"STEM2":cmd(....write=False)}]},
             {"ROOT2":cmd(...,read=False)}
            ]

        defines tango attriobutes for the SCPI commands:
            ROOT:STEN:LEAF
            ROOT:STEM:LEAF?
            ROOT:STEN2?
            ROOT2
        """
        super().__init__(*args)
        self.protocol = SCPIProtocol(self.transport)
        for scpi_attr in self.get_scpi_attrs():
            self._process_one(scpi_attr)

    def _process_one(self,scpi_attr, stem=""):
        """Recursively work through the scpi_attrs attribute to add scpi commands as tango controls attributes."""
        if isinstance(scpi_attr, dict): #List of new sub stems
            for sub_stem in scpi_attr:
                self._process_one(scpi_attr[sub_stem],f"{stem}:{sub_stem}")
        elif isinstance(scpi_attr, list):
            for sub_stem in scpi_attr:
                self._process_one(sub_stem,stem)
        elif isinstance(scpi_attr, cmd):
            scpi_attr.create_attr(self,stem)
        else:
            raise SyntaxError(f"Cannot understand how to use {type(scpi_attr)} to make scpi attrobutes")

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

    @attribute
    def operation_status_enable(self):
        """Read/write the operational status enable register.

        Args:
            mask (int):
                Bitwise mask to set.

        Returns:
            int:
                Bitwise mask set
        """
        return int(self.protocol.query("STAT:OPER:ENAB?"))

    @operation_status_enable.write
    def operation_status_enable(self, mask):
        self.protocol.write(f"STAT:OPER:ENAB {mask:d}")

    @attribute
    def operation_status_condition(self):
        """Read the operational status condition register.

        Returns:
            int:
                Bitwise value from the condtion register.
        """
        return int(self.protocol.query("STAT:OPER:COND?"))

    @attribute
    def operation_status_event(self):
        """Read the operational status condition register.

        Returns:
            int:
                Bitwise value from the condtion register.
        """
        return int(self.protocol.query("STAT:OPER:EVENT?"))

    @attribute
    def measurement_status_enable(self):
        """Read/write the measuremental status enable register.

        Args:
            mask (int):
                Bitwise mask to set.

        Returns:
            int:
                Bitwise mask set
        """
        return int(self.protocol.query("STAT:MEAS:ENAB?"))

    @measurement_status_enable.write
    def measurement_status_enable(self, mask):
        self.protocol.write(f"STAT:MEAS:ENAB {mask:d}")

    @attribute
    def measurement_status_condition(self):
        """Read the measuremental status condition register.

        Returns:
            int:
                Bitwise value from the condtion register.
        """
        return int(self.protocol.query("STAT:MEAS:COND?"))

    @attribute
    def measurement_status_event(self):
        """Read the measuremental status condition register.

        Returns:
            int:
                Bitwise value from the condtion register.
        """
        return int(self.protocol.query("STAT:MEAS:EVENT?"))

    @attribute
    def questionable_status_enable(self):
        """Read/write the questionableal status enable register.

        Args:
            mask (int):
                Bitwise mask to set.

        Returns:
            int:
                Bitwise mask set
        """
        return int(self.protocol.query("STAT:QUES:ENAB?"))

    @questionable_status_enable.write
    def questionable_status_enable(self, mask):
        self.protocol.write(f"STAT:QUES:ENAB {mask:d}")

    @attribute
    def questionable_status_condition(self):
        """Read the questionableal status condition register.

        Returns:
            int:
                Bitwise value from the condtion register.
        """
        return int(self.protocol.query("STAT:QUES:COND?"))

    @attribute
    def questionable_status_event(self):
        """Read the questionableal status condition register.

        Returns:
            int:
                Bitwise value from the condtion register.
        """
        return int(self.protocol.query("STAT:QUES:EVENT?"))

    def get_scpi_attrs(self):
        """Get a list of SCPI commands to be converted to attributes."""
        return getattr(self,"scpi_attrs",[])




if __name__=="__main__":
    SCPI.run_server()
