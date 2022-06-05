# -*- coding: utf-8 -*-
"""
Tango driver for a Keithley 24xx based on a SCPI device
"""
from dataclasses import dataclass
from typing import Optional, Mapping

import numpy as np

import tango
from tango.server import device_property
from stoner_tango.instr.base import SCPI
from stoner_tango.util.decorators import  SCPI_Instrument, pipe
from stoner_tango.util.funcs import ExtractFloats

@dataclass
class DataBuffer:

    """Represents a data buffer."""

    voltage:Optional[np.ndarray] = None
    current:Optional[np.ndarray] = None
    resistance:Optional[np.ndarray] = None
    times:Optional[np.ndarray] = None
    status:Optional[np.ndarray] = None

    def __init__(self,*args,**kargs):
        super().__init__(*args,**kargs)
        mapping:Mapping[str,str]={"VOLT":"voltage","CURR":"current","RES":"resistance","TST":"times","STAT":"status"}

@SCPI_Instrument
class K24XX(SCPI):

    """Tango server class for a Keithley 24xx Source Meter."""

    @pipe
    def Waveform(self)->DataBuffer:
        """Write a source waveform or read the buffer back gain.

        Returns:
            DataBuffer: voltage,current,resistance, readings."""
        buffer=ExtractFloats(self.protocol.query("TRAC:DATA?", text=False))
        elements=[x.strip() for x in self.protocol.query("FORM:SENS:ELEM?").split(",")]
        self.protocol.write("TRAC:CLE")
        dim1=len(elements)
        dim2=buffer.size//dim1
        buffer=np.reshape(buffer,(dim1,dim2))
        ret=DataBuffer()
        for elem,row in zip(elements,buffer):
            setattr(ret,ret.mapping[elem],row)
        if ret.resistance is None and ret.voltage and ret.current:
            ret.resistance=ret.voltage/ret.current
        return ret

    @Waveform.write
    def Waveform(self,data:DataBuffer):
        """Write a source waveform or read the buffer back gain.

        Args:
            DataBuffer: voltage or current readings to program.
        """
        if data.voltage is not None:
            values=data.voltage
            mode="VOLT"
        else:
            values=data.current
            mode="CURR"
        for i in range(int(np.ceil(values/100))):
            section=",".join(values[i*100:(1+1)*100])
            extra="" if i==0 else ":APP"
            cmd=f":SOUR:LIST:{mode}{extra} {section}"
            self.protocol.wite(cmd)

    def operationStatusCondition__posthook(self, value):
        """Update status based on reading from event register."""
        if value&1024:
            self.state=tango.DevState.ON
        if value&96:
            self,state=tango.DevState.STANDBY
        if value&84:
            self.staate=tango.DevState.MOVING
        return value



class Keithley24xx(tango.DeviceProxy):

    """The client side class of a Keithley Source Meter."""

    def __init__(self,*args,**kargs):
        super().__init__(*args,**kargs)
        if "KEITHLEY INSTRUMENTS INC.,MODEL 24" not in self.idn:
            raise TypeError("This class can only support Keithley 24xx instruments")







if __name__ == "__main__":
    K24XX.run_server()
