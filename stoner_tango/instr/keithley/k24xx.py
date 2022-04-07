# -*- coding: utf-8 -*-
"""
Tango driver for a Keithley 24xx based on a SCPI device
"""
from tango.server import device_property, server_run

from stoner_tango.instr.base.SCPI import SCPI
from stoner_tango.util.decorators import command, attribute, SCPI_Instrument, Command
from stoner_tango.util import sfmt, sbool

@SCPI_Instrument
class K24XX(SCPI):

    """Tango server class for a Keithley 24xx Source Meter."""
    

if __name__ == "__main__":
    K24XX.run_server()
