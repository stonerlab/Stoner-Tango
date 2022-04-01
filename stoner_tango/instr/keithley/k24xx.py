# -*- coding: utf-8 -*-
"""
Tango driver for a Keithley 24xx based on a SCPI device
"""
from tango.server import device_property, server_run

from stoner_tango.instr.base.SCPI import SCPI
from stoner_tango.util.decorators import command, attribute


class K24XX(SCPI):
    
    """Tango server class for a Keithley 24xx Source Meter."""
    
    ## Sense subsustem
    @attribute
    def current_sense_autorange(self):
        """Autorange the current measurements.
        
            Args:
                auto (bool):
                    Set True if autoranging
            
            Returns:
                bool:
                    True if autoranging
        """
        return self.protocol.query("SENS:CURR:RANG:AUTO?")
        
    @current_sense_autorange.write
    def current_sense_autorange(self, auto):
        value="ON" if auto else "OFF"
        self.protocol.write(f"SENS:CURR:RANG:AUTO {value}")
    
    
if __name__=="__main__":
    K24XX.run_server()