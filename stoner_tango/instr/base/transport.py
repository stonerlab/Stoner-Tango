"""
Transport classes deal with communicating with an instrument via a hardware interface such as GPIB, Serial, Ethernet etc.
"""
import sys
from typing import Any
from abc import ABCMeta
import threading

import pyvisa as pv
import tango

from ..exceptions import NotConnectedError, NoSuchInstrumentError

class BaseTransport(metaclass=ABCMeta):

    """The abstract base class for transports to define the interface."""

    def __init__(self, dev):
        """Construct the transport, recording the tango.server.Device in an attribute."""
        self._dev=dev

    def __enter__(self):
        """Context manager to ensure4 instrument is connected."""
        return self.connect(self.timetout)

    def __exit__(self):
        """Context manager exit, disconnect from instrument."""
        self.diconnect()

    @property
    def state(self):
        """Proxy through to tango device state."""
        return getattr(self._dev,"state",tango.DevState.OFF)

    @state.setter
    def state(self, state):
        """Proxy through to tango device state"""
        if hasattr(self._dev,"state"):
            self._dev.state=state

    @property
    def status(self):
        """Proxy for tango status."""
        return getattr(self._dev,"status","Not connected")

    @status.setter
    def status(self, value):
        """Proxy through to tango status."""
        if hasattr(self._dev,"status"):
            self._dev.status=value

    @property
    def log_debug(self):
        return getattr(self._dev,"log_debug",sys.stderr)

    @property
    def log_error(self):
        return getattr(self._dev,"log_error",sys.stderr)

    def debug(self,msg:str)->None:
        """Send a message to our debug stream."""
        if hasattr(self._dev,"status"):
            print(msg,file=self._dev.log_debug)

    def connect(self, timeout:float=5.0)->Any:
        """Connect to the instrument and return a connection object."""
        pass

    def disconnect(self)->None:
        """Disconenct from the instrument."""
        pass

    def readbytes(self, bytes: int)->bytes:
        """Read from instrument up to a maximum limit of bytes."""
        raise NotImplementedError()

    def read(self, bytes:int =-1)->str:
        """Read a single line as a string from an instrument."""
        raise NotImplementedError()

    def write(self,data:str)->int:
        """Write a string to the instrument and return the bytes transferred."""
        raise NotImplementedError()

    def writebytes(self, data:bytes)->int:
        """Write a bytes array to the instrument and return the number of bytes transferred."""
        raise NotImplementedError()

    def query(self, data, bytes=-1)->str:
        """Perform a write then read operation."""
        self.write(data)
        return self.read(bytes=bytes)

class VisaTransport(BaseTransport):

    """An instrument communications transport that uses PyVISA for the comms.

    By default when the :py:attr:`VisaTransport.name` attribute is set, this class will attempt to start a background thread
    to keep a connection open to the instrument. This can be suppressed by setting :pyLattr:`VisaTransport.persist`
    before setting the the :py:attr:`VisaTransport.name` attribiute.

    The :py:class:`VisaTransport` can also be used as a context manager - it will as necessary open a new connection to
    the instrument, or re-use the existing one.

    Usage:

        Careate the transport ovject and then read and write, or query it.::
            transport=VisaTransport(name='GPIB0::10::INSTR')
            print(transport.query("*IDN?"))

        Altenatively, use it like a context manager::
            with VisaTransport(name="GPIB0::10::INSTR") as transport:
                print(transport.query("*IDN?"))
    """

    def __init__(self, dev, **kargs):
        """Construct the transport instance from kwargs."""
        super().__init__(dev) # Store the tango Device

        # Setup our resource manager first
        self._rm=pv.ResourceManager()
        self.timeout=1.0
        self._stopThreadEvent = None
        self._awakeThreadEvent = None
        self._thread=None
        self._name = ""
        self._resource = None
        self._closeme=lambda :None
        self.persist=True
        self.max_read=65536

        for kw, val in kargs.items():
            if hasattr(self,kw):
                setattr(self,kw,val)

    def __enter__(self):
        """Reuse existing resource if open."""
        try:
            return self.resource
        except ValueError:
            self._closeme=self.disconnect
            return self.connect()

    def __exit__(self):
        """Diconect if necessary."""
        self._closeme()



    def _start_thread(self):
        """Start up thread to keep an instrument open and alive."""
        self._stopThreadEvent=threading.Event()
        self._stopThreadEvent.clear()
        self._awakeThreadEvent=threading.Event()
        self._awakeThreadEvent.clear()
        self._thread = threading.Thread(target=self._keep_connected)
        self._thread.setDaemon(True)
        self._thread.start()
        self._stopThreadEvent.wait(0.1)

    def _stop_thread(self):
        """Shutdown the connection thread."""
        if self._thread:
            self.debug(f"Requesting Thread stop for {self.name}")
            self._stopThreadEvent.set()
            self._awakeThreadEvent.set()
            self._thread.join()

    def _keep_connected(self):
        """Run in a separate thread to keep an instrument connection alive."""
        loop=0
        while not self._stopThreadEvent.isSet():
            try:
                self.connect()
                loop=0
                self._awakeThreadEvent.wait()
                self.debug(f"Restarted connection thread for {self.name}")
                self._awakeThreadEvent.clear()
                self.disconnect()
            except (SyntaxError, ImportError) as e:
                raise e
            except Exception as e:
                loop+=1
                loop%=3600
                if loop==0:
                    print(f"Persistent connection failure for {self.name}", file=self.log_error)
                self.state=tango.DevState.FAULT
                self.status=f"Error {e} in connecting"
                self._resource=None
                self._awakeThreadEvent.wait(self.timeout)
        # Cleanrup the connecton
        self.debug(f"Finishing connection manager thread for {self.name}")
        self._thread = None

    @property
    def resource(self):
        """Throw an error if self._resource is not set!"""
        if not isinstance(self._resource, pv.Resource):
            self.debug(f"Attempted to access unconnected instrument {self.name}.")
            raise NotConnectedError(f"No active connection to {self.name}")
        return self._resource

    @property
    def name(self)->str:
        """Return the VISA reference name."""
        return self._name

    @property
    def interface(self)->str:
        """Return the name of VISA Interface object."""
        return f"{self.name.split(':')[0]}::INTFC"

    @name.setter
    def name(self, name:str):
        """Set the visa reference name and start connection."""
        if name not in self._rm.list_resources():
            raise NoSuchInstrumentError(f"{name} is not in the list of current VISA references {','.join(self._rm.list_resources())}")
        if self.persist:
            if self._thread:
                self._stop_thread()
            self._name=name
            self._start_thread()


    def connect(self,timeout=1.0):
        """Connect to the resource and return the visa Resource."""
        self._resource=self._rm.open_resource(self.name)
        self.state=tango.DevState.ON
        self.status=f"Connect to {self.name}"
        self.debug(f"Connected to {self.name} inside thread")
        return self._resource

    def disconnect(self):
        """Disconnect from the resource."""
        self._resource.close()
        self._resource=None
        self.state = tango.DevState.OFF
        self.status = f"Disconnected for {self.name}"

    def readbytes(self, bytes: int)->bytes:
        """Read from instrument up to a maximum limit of bytes."""
        data=self.resource.read_bytes(bytes)
        if getattr(self._dev,"_debug",False):
            self.debug(f"{self.name} >>> {data.decode()}")
        return data

    def read(self, bytes:int =-1)->str:
        """Read a single line as a string from an instrument."""
        data =  self.resource.read()
        if getattr(self._dev,"_debug",False):
            self.debug(f"{self.name} >>> {data}")
        return data


    def write(self,data:str)->int:
        """Write a string to the instrument and return the bytes transferred."""
        if getattr(self._dev,"_debug",False):
            self.debug(f"{self.name} <<< {data}")
        return self.resource.write(data)

    def writebytes(self, data:bytes)->int:
        """Write a bytes array to the instrument and return the number of bytes transferred."""
        if getattr(self._dev,"_debug",False):
            self.debug(f"{self.name} <<< {data.decode()}")
        data = self.resource.write_raw(data)
        return data


class GPIBTransport(VisaTransport):

    """Provide a VisaTransport specialised for GPIB operations."""

    @property
    def stb(self):
        """Read the status bytes from the instrument."""
        return self.resource.read_stb()

    @property
    def addr(self):
        """Return the address as an integer."""
        return int(self.name.split("::")[1])

    def send(self,data:bytes)->pv.constants.StatusCode:
        """Send a set of bytes to the interface."""
        if not isinstance(data,bytes):
            data=bytes(data)
        with self._rm.open_resource(self.interface) as interface:
            return interface.send_command(data)[1]

    def IFC(self)->pv.constants.StatusCode:
        """Semd IFC tot he interface."""
        with self._rm.open(self.interface) as interface:
            return interface.send_ifc()[1]

    def SDC(self)->pv.constants.StatusCode:
        """Send the selective device clear to the intrument."""
        return self.send([63,32|self.addr,4,63])[1]

    def GTL(self)->pv.constants.StatusCode:
        """Send the set to local to the intrument."""
        return self.send([63,32|self.addr,1,63])[1]

    def GET(self)->pv.constants.StatusCode:
        """Send the group execute trigger to the intrument."""
        return self.send([63,32|self.addr,8,63])[1]
