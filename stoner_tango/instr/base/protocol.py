# -*- coding: utf-8 -*-
"""
Protocol classes to ensure clean communications between the controller and instrument and error recovery.
"""
from typing import Union
import time
import re

import tango

from .transport import BaseTransport, VisaTransport, GPIBTransport
from ..exceptions import CommandError, NoDataError

class Raw:

    """Minimal data preparation and interpretation.

    This protocol understands about termination characters and the need to set a rest period of time after writing to the isntrument
    before doing anything else.

    Attributes:

        terminator (str):
            Termination character(s) to append to the string.
        sleep (float):
            Time in seconds to wait after writing to the instrument.
    """

    def __init__(self, transport, **kargs):
        """Setup the protocol class."""
        if not isinstance(transport, BaseTransport):
            raise ValueError(f"transport parameter should be a BaseTransport instance not a {type(transport)}")
        self.terminator="\n"
        self._transport=transport
        self._dev=transport._dev
        self.sleep=self._dev.get_property("sleep")
        for kw,val in kargs.items():
            if hasattr(self, kw):
                setattr(self,kw,val)

    def read(self,bytes:int=-1)->str:
        """Return the data from the instrument, stripping off the terminator."""
        data=self._transport.read(bytes).strip(self.terminator)
        return data

    def write(self,data:str)->int:
        """Send data to the transport, sorting out terminator."""
        ret = self._transport.write(data)
        time.sleep(self.sleep)
        return ret

    def readbytes(self,bytes:int)->bytes:
        """readbytes has to read a fixed number of bytes regardless of terminator presence."""
        return self._transport.readbytes(bytes)

    def writebytes(self,data:bytes)->int:
        """Wraps the transport writebytes."""
        ret =  self._transport.writebytes(data)

        time.sleep(self.sleep)
        return ret

    def query(self,data,bytes=-1, text=True)->Union[str,bytes]:
        """Back and forth transaction."""
        self.write(data)
        if text:
            return self.read(bytes)
        return self.readbytes(bytes)



class SCPIProtocol(Raw):

    """A variant protocol for doing SCPI with error handling."""

    err_pat=re.compile(r"(?P<code>[\-0-9]*),[\"\'](?P<msg>[^\"\']*)[\"\']")

    def write(self,data:str)->int:
        """Check the status byte after writing to the intrument."""
        ret=super().write(data)
        if hasattr(self._transport,"stb"):
            if (self._transport.stb & 4)==4:
                err_code,err_msg=True,""
                errs=""
                while err_code!=0:
                    self._transport.state=tango.DevState.ALARM
                    self._transport.status=f"Error after writing {data}"
                    error=self._transport.query(":SYST:ERR?")
                    match=self.err_pat.match(error)
                    if not match:
                        err_code=0
                        continue
                    err_code=float(match.groupdict()["code"])
                    err_msg=match.groupdict()["msg"]
                    print(f"SCPI Error: {error}", file=self._transport.log_debug)
                    errs+=error
                    time.sleep(self.sleep)
                self._transport.write("*CLS")
                raise CommandError(data)
            else:
                self._transport.statu="OK"
                self._transport.state=tango.DevState.ON
        return ret

    def read(self, bytes:int=-1)->str:
        if hasattr(self._transport,"stb") and self._transport.stb & 16:
            return super().read(bytes)
        print(f"No message recieved available from {self._transport.name}", file=self._dev.log_debug)
        raise NoDataError("Failed to find any data to read.")

    def readbytes(self,bytes:int)->bytes:
        """readbytes has to read a fixed number of bytes regardless of terminator presence."""
        if hasattr(self._transport,"stb") and self._transport.stb & 16:
            return super().readbytes(bytes)
        print(f"No message recieved available from {self._transport.name}", file=self._dev.log_debug)
        raise NoDataError("Failed to find any data to read.")


class OITraditional(Raw):

    """This protocol class is designed for the Oxford Instruments Serial over GPIB patter. Every command repsons with a letter
    that matches the letter sent and signals an error with  a ?."""

    def __init__(self, transport, **kargs):
        """Setup for the OI protocol. Force the terminator to be \r and set a sleep."""
        kargs.update({"terminator":"\r", "sleep":0.1})
        super().__init__(transport, **kargs)
        self._results=[]

    def write(self, data:str):
        """All writes should have a read after them."""
        data=data.strip(self.terminator)+self.terminator
        ret = super().write(data)
        result=self.read()
        if len(result)==0 or result[0]!=data[0]:
            self._transport.state=tango.DevState.ALARM
            self._transport.status=f"Sent {data} but got {result} back!"
            print("Mimatched command and response {data}->{result}", file=self._dev.log_debug)
            raise CommandError(f"Mimatching commands {data} and {result}")
        if len(result)  and result[-1]=="?":
            self._transport.state=tango.DevState.ALARM
            self._transport.status=f"{data} resulted in a command error!"
            print(f"{data} resulted in a command error!", file=self._dev.log_debug)
            raise CommandError(f"{data} resulted in a command error!")
        if len(result)>1:
            result=result[1:]
        self._results.append(result)
        self._transport.state=tango.DevState.ON
        self._transport.status="OK"
        return ret

    def read(self, bytes:int=-1)->str:
        """Read the first response of the results stack."""
        if len(self._results)>0:
            return self._results.pop(0)
        self._transport.state=tango.DecState.ALARM
        self._transport.status="Tried reading more responses than stored."
        print("Tried reading more responses than stored.", file=self._dev.log_debug)
        raise CommandError("Tried reading more responses than stored.")
