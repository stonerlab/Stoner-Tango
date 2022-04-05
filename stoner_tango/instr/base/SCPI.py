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
from stoner_tango.util.decorators import command, attribute, pipe
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
    def dict(self)->str:
        """Return the current objects dictionary.
        
        Returns:
            str:
                __dict__
        """
        return pformat(self.__class__.__dict__)
        

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


class SCPI(IEEE488_2):

    """Further wraps the IEEE488.2 Instrument with a SCPI proptocol handler."""

    def __init__(self,*args, **kargs):
        """Construct the SCPI instrument.
        """
        super().__init__(*args)
        self.protocol = SCPIProtocol(self.transport)
        for item in getattr(self,"scpi_attrs",[]):
            self._process_one(item)
            
    def _process_one(self,item,cmd=""):
        if isinstance(item, list):
            for sub_item in item:
                self._process_one(sub_item,cmd)
        elif isinstance(item, dict):
            for key,sub_item in item.items():
                self._process_one(sub_item,f"{cmd}:{key}")
        elif isinstance(item,Command):
            klass=self.__class__
            r_meth=getattr(klass,f"read_{item.name}", None)
            w_meth=getattr(klass,f"write_{item.name}", None)
            if r_meth is None and item.read:
                def f_read(self):
                    return item.reader(self.protocol.query(f"{cmd}?"))
                setattr(klass,f"read_{item.name}",f_read)
                r_meth=getattr(self,f"read_{item.name}")
            if w_meth is None and item.write:
                def f_write(self, value):
                    self.protocol.write(f"{cmd} {sfmt(value)}")
                setattr(klass,f"write_{item.name}",f_write)
                w_meth=getattr(self,f"write_{item.name}")
            attr=AttrData.from_dict({
                "name":item.name,
                "dtype":TO_TANGO_TYPE[item.dtype],
                "unit":item.unit,
                "label":item.label,
                'doc':item.doc,
                'fget':r_meth if item.read else None,
                'fset':w_meth if item.write else None,
                }).to_attr()
            self._add_attribute(attr, f"read_{item.name}",f"write_{item.name}" , f"is_{item.name}_allowed")
        else:
            raise TypeError("Error defining scpi attributes with {item}")
               

    @attribute
    def version(self):
        """Get the system version number.

        Returns:
            str:
                Version
        """
        return self.protocol.query("SYST:VERS?")

    @pipe
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

    # scpi_attrs=[{"STAT":[
    #     {"OPER":[
    #         {"ENAB":Command(name="operational_status_enable",
    #                         dtype=int,
    #                         doc="ead/write the operational status enable register.",
    #                         label="OP Status Enable")},
    #         {"COND":Command(name="operation_status_condition",
    #                         dtype=int,
    #                         doc="Read the operational status condition register.",
    #                         write=False,
    #                         label="OP Status condition")},
    #         {"EVEN":Command(name="operation_status_event",
    #                         dtype=int,
    #                         doc="Read the operational status event register.",
    #                         write=False,
    #                         label="OP Status event")},
            
    #         ]}
        
    #     ]}]

    @attribute
    def operation_status_enable(self):
        """Read/write the operational status enable register.

        Returns:
            int:
                Op Status Emable
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
                OP Status condition
        """
        return int(self.protocol.query("STAT:OPER:COND?"))

    @attribute
    def operation_status_event(self):
        """Read the operational status condition register.

        Returns:
            int:
                OP Status Event
        """
        return int(self.protocol.query("STAT:OPER:EVENT?"))

    @attribute
    def measurement_status_enable(self):
        """Read/write the measuremental status enable register.

        Returns:
            int:
                Measurement Status Enable
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
                Measurement Status Condition
        """
        return int(self.protocol.query("STAT:MEAS:COND?"))

    @attribute
    def measurement_status_event(self):
        """Read the measuremental status condition register.

        Returns:
            int:
                Measurement Status Event
        """
        return int(self.protocol.query("STAT:MEAS:EVENT?"))

    @attribute
    def questionable_status_enable(self):
        """Read/write the questionableal status enable register.

        Returns:
            int:
                Questionable Event Status Enable
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
                uestionable Event Status Condition
        """
        return int(self.protocol.query("STAT:QUES:COND?"))

    @attribute
    def questionable_status_event(self):
        """Read the questionableal status condition register.

        Returns:
            int:
                uestionable Event Status Occurance
        """
        return int(self.protocol.query("STAT:QUES:EVENT?"))

    def get_scpi_attrs(self):
        """Get a list of SCPI commands to be converted to attributes."""
        return getattr(self,"scpi_attrs",[])


if __name__=="__main__":
    SCPI.run_server()
