# -*- coding: utf-8 -*-
"""
Tango driver for a Keithley 24xx based on a SCPI device
"""
from tango.server import device_property
from stoner_tango.instr.base import SCPI
from stoner_tango.util.decorators import  SCPI_Instrument

@SCPI_Instrument
class K24XX(SCPI):

    """Tango server class for a Keithley 24xx Source Meter."""
       

if __name__ == "__main__":
    K24XX.run_server()
