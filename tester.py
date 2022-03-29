# -*- coding: utf-8 -*-
"""
Created on Sun Mar 27 21:42:29 2022

@author: rig
"""
from stoner_tango.instr.base.transport import GPIBTransport
from stoner_tango.instr.base.protocol import SCPIProtocol

g=GPIBTransport(None,name="GPIB0::10::INSTR")
p=SCPIProtocol(g,sleep=0.2)

print(p.query("*IDN?"))