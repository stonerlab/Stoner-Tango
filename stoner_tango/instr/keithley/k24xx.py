# -*- coding: utf-8 -*-
"""
Tango driver for a Keithley 24xx based on a SCPI device
"""
from tango.server import device_property, server_run

from stoner_tango.instr.base.SCPI import SCPI
from stoner_tango.util.decorators import command, attribute
from stoner_tango.util import sfmt, sbool


class K24XX(SCPI):

    """Tango server class for a Keithley 24xx Source Meter."""
    
    @attribute
    def I_sense_range(self):
        """Range level for current measurements.
    
        Range (0,1.0)
            
        Returns:
            float: I Range in A
        """
        return float(self.protocol.query("SENS:CURR:RANG?"))
    
    @I_sense_range.write
    def I_sense_range(self,value):
        self.protocol.write(f"SENS:CURR:RANGE {sfmt(value)}")

    @attribute
    def I_sense_autorange(self):
        """Auto range for current measurements.
                   
        Returns:
            bool: Aitorange I
        """
        return float(self.protocol.query("SENS:CURR:RANG:AUTO?"))
    
    @I_sense_autorange.write
    def I_sense_autorange(self,value):
        self.protocol.write(f"SENS:CURR:RANGE:AUTO {sfmt(value)}")
        
    @attribute
    def I_sense_autorange_limit(self):
        """Limit for autoranging current
        
        Range(0,1.0)
            
        Returns:
            float: I Autorange limit in A
        """
        return float(self.protocol.query("SENS:CURR:RANG:AUTO:LLIM?"))
     
    @I_sense_autorange_limit.write
    def I_sense_autorange_limit(self,value):
        self.protocol.write(f"SENS:CURR:RANGE:AUTO:LLIM {sfmt(value)}")
   
    @attribute
    def I_sens_nplc(self):
        """Number of power line cycles to measure current for.
        
        Range (0.01,10.0)
            
        Returns:
            float: NLPC
        """
        return float(self.protocol.query("SENS:CURR:NPLC?"))
    
    @I_sens_nplc.write
    def I_sens_nplc(self,value):
        self.protocol.write(f"SENS:CURR:NPLC {value:.2f}")

    @attribute
    def V_sense_range(self):
        """Range level for voltage measurements.
    
        Range (0.2,200)
            
        Returns:
            float: I Range in A
        """
        return float(self.protocol.query("SENS:VOLT:RANG?"))
    
    @V_sense_range.write
    def V_sense_range(self,value):
        self.protocol.write(f"SENS:VOLT:RANGE {sfmt(value)}")

    @attribute
    def V_sense_autorange(self):
        """Auto range for voltage measurements.
                   
        Returns:
            bool: Autorange V
        """
        return float(self.protocol.query("SENS:VOLT:RANG:AUTO?"))
    
    @V_sense_autorange.write
    def V_sense_autorange(self,value):
        self.protocol.write(f"SENS:VOLT:RANGE:AUTO {sfmt(value)}")
        
    @attribute
    def V_sense_autorange_limit(self):
        """Limit for autoranging voltage
        
        Range(0,200.0)
            
        Returns:
            float: I Autorange limit in A
        """
        return float(self.protocol.query("SENS:VOLT:RANG:AUTO:LLIM?"))
     
    @V_sense_autorange_limit.write
    def V_sense_autorange_limit(self,value):
        self.protocol.write(f"SENS:VOLT:RANGE:AUTO:LLIM {sfmt(value)}")
   
    @attribute
    def V_sens_nplc(self):
        """Number of power line cycles to measure voltage for.
        
        Range (0.01,10.0)
            
        Returns:
            float: NLPC
        """
        return float(self.protocol.query("SENS:VOLT:NPLC?"))
    
    @V_sens_nplc.write
    def V_sens_nplc(self,value):
        self.protocol.write(f"SENS:CURR:NPLC {value:.2f}")

if __name__ == "__main__":
    K24XX.run_server()
