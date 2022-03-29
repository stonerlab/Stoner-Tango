#  This is a reworking of the ALBA PyVisa instrument server

import tango
import sys
import array

## Needed PyVisa library from http://pyvisa.sourceforge.net/
from visa import *
from pyvisa import *

import threading

class PyVisa(tango.DeviceImpl):
    
    """Use PyVISA to to implement a nase class for reading/writing to VISA based instruments.

    Device States:    
        DevState.ON :     Device is Open (By default)
        DevState.FAULT :  The device is in some fault state
        DevState.OFF :    The device is OFF.
    """

    ## The instrument to talk with
    __instrument = None
    ## The different formats
    FORMATS = ["ASCII", "SINGLE", "", "DOUBLE", "BIG_ENDIAN"]

    def startThread(self, time=1):
        """Start thread in 'daemon' mode.
        
        Keyword Args:
            time (int):
                Time to wait in seconds (default 1)

        The target of the thread is the connect method which will try
        to keep the device server connected to the device.
        """
        self.setReconnectTimeWait(time)
        if hasattr(self, '__thread') and self.__thread and self.__thread.isAlive():
            self.debug_stream("In %s::startTherad(): Trying to start threading when is already started."%self.get_name())
            return
        self.__threaded = True
        ## The communication between threads
        self.__joiner = threading.Event()
        self.__joiner.clear()
        self.__connectionEvent = threading.Event()#set when communications fails
        self.__connectionEvent.clear()
        self.__thread = threading.Thread(target=self.connect)
        self.__thread.setDaemon(True)
        self.__thread.start()
        self.__joiner.wait(0.1)

    def stopThread(self):
        """ It stops the thread. """
        if hasattr(self, '__joiner'):
            self.__joiner.set()
        if hasattr(self, '__connectionEvent'):
            self.__connectionEvent.set()
        if hasattr(self, '__thread'):
            self.__thread.join()

    def connect(self):
        """
        Main method of the thread.
        This method will check the connection with the device and
        set the state to ON or FAULT accordingly.
        """
        repeatMsgCnt = 0
        repeatMsg = ""
        while not self.__joiner.isSet():
            try:
                self.set_state(tango.DevState.INIT)
                #1: connect to the instrument
                self.__instrument = instrument(self.VisaName)
                #2: setup the state
                self.set_state(tango.DevState.ON)
                self.machineStatus()
                #3: passive sleep until a connection requires the action of this thread
                self.debug_stream("In %s::connect(): Connectivity thread go to sleep"%(self.get_name()))
                self.__connectionEvent.wait()
                self.debug_stream("In %s::connect(): Connectivity thread wake up"%(self.get_name()))
                self.__connectionEvent.clear()
            except Exception, e:
                self.set_state(tango.DevState.FAULT)
                self.machineStatus(e)
                msg = "In %s::connect(): (re)connection thread exception: %s"%(self.get_name(),e)
                if repeatMsg == msg and not repeatMsgCnt == sys.maxint:
                    repeatMsgCnt += 1
                else:
                    if not repeatMsgCnt == 0:#not necessary to say it is more than sys.maxint
                        self.error_stream("In %s::connect(): last message repeated %d times"%(self.get_name(),repeatMsgCnt))
                    self.error_stream(msg)
                    repeatMsg = msg
                    repeatMsgCnt = 0
                self.__connectionEvent.wait(self.getReconnectTimeWait())
        #out the loop means the thread has to finish and join the main one.
        self.debug_stream("In %s::connect(): thread exiting"%self.get_name())

    def getReconnectTimeWait(self):
        return self.__reconnectTimeWait

    def setReconnectTimeWait(self, time):
        self.__reconnectTimeWait = time


    def machineStatus(self,e=None):
        bar = "The device is in %s state."%(self.get_state())
        if not e == None:
            bar += "\n"+str(e)
        self.set_status(bar)


#------------------------------------------------------------------
#    Device constructor
#------------------------------------------------------------------
    def __init__(self, cl, name):
        tango.DeviceImpl.__init__(self, cl, name)
        PyVisa.init_device(self)
        self.__instrument = None

#------------------------------------------------------------------
#    Device destructor
#------------------------------------------------------------------
    def delete_device(self):
        #print "[Device delete_device method] for device", self.get_name()
        self.stopThread()
        self.__instrument = None
        self.timeout_set = False


#------------------------------------------------------------------
#    Device initialization
#------------------------------------------------------------------
    def init_device(self):
        """
        At the init stage the state is ON and a thred will be
        started in order to check periodically the state of the device.
        """
        self.debug_stream("In ", self.get_name(), "::init_device()")
        self.set_state(tango.DevState.ON)
        self.machineStatus()
        self.get_device_properties(self.get_device_class())
        #print "All properties set, creating the device "+self.VisaName
        try:
            #TODO: Not a try, a thread how allows connection in background
            self.startThread(1)
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            return

#------------------------------------------------------------------
#    Always excuted hook method
#------------------------------------------------------------------
    def always_executed_hook(self):
        self.debug_stream("In ", self.get_name(), "::always_excuted_hook()")

#==================================================================
#
#    PyVisa read/write attribute methods
#
#==================================================================
#------------------------------------------------------------------
#    Read Attribute Hardware
#------------------------------------------------------------------
    def read_attr_hardware(self, data):
        self.debug_stream("In ", self.get_name(), "::read_attr_hardware()")



#------------------------------------------------------------------
#    Read Timeout attribute
#------------------------------------------------------------------
    def read_Timeout(self, attr):
        self.debug_stream("In ", self.get_name(), "::read_Timeout()")
        
        #    Add your own code here
        try:
            attr_Timeout_read = self.__instrument.timeout
            attr.set_value(attr_Timeout_read)
        except Exception,e:
            self.error_stream("In ", self.get_name(), "::read_Timeout() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Write Timeout attribute
#------------------------------------------------------------------
    def write_Timeout(self, attr):
        self.debug_stream("In ", self.get_name(), "::write_Timeout()")
        data=[]
        attr.get_write_value(data)
        self.warn_stream("%s: Timeout attribute value = %s"%(self.VisaName,data))

        #    Add your own code here
        try:
            timeout = data[0]
            if timeout == 0:
                timeout = 0.1
            self.__instrument.timeout = timeout
        except Exception,e:
            self.error_stream("In %s::write_Timeout() Exception: %s"%(self.get_name(),e))
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()
            return


#------------------------------------------------------------------
#    Read ChunkSize attribute
#------------------------------------------------------------------
    def read_ChunkSize(self, attr):
        self.debug_stream("In ", self.get_name(), "::read_ChunkSize()")
        
        #    Add your own code here

        try:
            attr_ChunkSize_read = self.__instrument.chunk_size
            attr.set_value(attr_ChunkSize_read)
        except Exception,e:
            self.error_stream("In ", self.get_name(), "::read_ChunkSize() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Write ChunkSize attribute
#------------------------------------------------------------------
    def write_ChunkSize(self, attr):
        self.debug_stream("In ", self.get_name(), "::write_ChunkSize()")
        data=[]
        attr.get_write_value(data)
        #print self.VisaName+": ChunkSize attribute value = ", data

        #    Add your own code here
        try:
            self.__instrument.chunk_size = data[0]
        except Exception,e:
            self.error_stream( "In ", self.get_name(), "::write_ChunkSize() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Read ValuesFormat attribute
#------------------------------------------------------------------
    def read_ValuesFormat(self, attr):
        self.debug_stream( "In ", self.get_name(), "::read_ValuesFormat()")
        
        #    Add your own code here
        try:
            index = self.__instrument.values_format
            attr_ValuesFormat_read = self.FORMATS[index]
            attr.set_value(attr_ValuesFormat_read)
        except Exception,e:
            self.error_stream( "In ", self.get_name(), "::read_ValuesFormat() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Write ValuesFormat attribute
#------------------------------------------------------------------
    def write_ValuesFormat(self, attr):
        self.debug_stream( "In ", self.get_name(), "::write_ValuesFormat()")
        data=[]
        attr.get_write_value(data)
        #self.debug_stream(self.VisaName+": ValuesFormat attribute value = ", data)

        #    Add your own code here
        try:
            format = data[0]
            self.__instrument.values_format = self.FORMATS.index(format)
        except Exception,e:
            self.error_stream( "In ", self.get_name(), "::write_ValuesFormat() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Read TermChars attribute
#------------------------------------------------------------------
    def read_TermChars(self, attr):
        self.debug_stream( "In ", self.get_name(), "::read_TermChars()")
        
        #    Add your own code here
        
        try:
            chars = self.__instrument.term_chars
            if chars == None:
                raise Exception("TermChars not defined")
            chars = chars.replace("\r", "CR")
            chars = chars.replace("\n", "LF")
            attr_TermChars_read = chars
            attr.set_value(attr_TermChars_read)
        except Exception,e:
            self.error_stream( "In %s::read_TermChars() Exception: %s"%(self.get_name(),e))
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Write TermChars attribute
#------------------------------------------------------------------
    def write_TermChars(self, attr):
        self.debug_stream("In ", self.get_name(), "::write_TermChars()")
        data=[]
        attr.get_write_value(data)
        #self.debug_stream(self.VisaName+": TermChars attribute value = ", data)

        #    Add your own code here
        try:
            chars = data[0]
            chars = chars.replace("CR", "\r")
            chars = chars.replace("LF", "\n")
            self.__instrument.term_chars = chars
        except Exception,e:
            self.error_stream( "In ", self.get_name(), "::write_TermChars() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Read SendEnd attribute
#------------------------------------------------------------------
    def read_SendEnd(self, attr):
        self.debug_stream("In ", self.get_name(), "::read_SendEnd()")
        
        #    Add your own code here
        
        try:
            attr_SendEnd_read = self.__instrument.send_end
            attr.set_value(attr_SendEnd_read)
        except Exception,e:
            self.error_stream( "In ", self.get_name(), "::read_SendEnd() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Write SendEnd attribute
#------------------------------------------------------------------
    def write_SendEnd(self, attr):
        self.debug_stream("In ", self.get_name(), "::write_SendEnd()")
        data=[]
        attr.get_write_value(data)
        #print self.VisaName+": SendEnd attribute value = ", data

        #    Add your own code here
        try:
            self.__instrument.send_end = data[0]
        except Exception,e:
            self.error_stream( "In ", self.get_name(), "::write_SendEnd() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Read Delay attribute
#------------------------------------------------------------------
    def read_Delay(self, attr):
        self.debug_stream("In ", self.get_name(), "::read_Delay()")
        
        #    Add your own code here
        
        try:
            attr_Delay_read = self.__instrument.delay
            attr.set_value(attr_Delay_read)
        except Exception,e:
            self.error_stream( "In ", self.get_name(), "::read_Delay() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#------------------------------------------------------------------
#    Write Delay attribute
#------------------------------------------------------------------
    def write_Delay(self, attr):
        self.debug_stream( "In ", self.get_name(), "::write_Delay()")
        data=[]
        attr.get_write_value(data)
        #print self.VisaName+": Delay attribute value = ", data

        #    Add your own code here
        try:
            self.__instrument.delay = data[0]
        except Exception,e:
            self.error_stream( "In ", self.get_name(), "::write_Delay() Exception: %s"%e)
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()



#==================================================================
#
#    PyVisa command methods
#
#==================================================================

#------------------------------------------------------------------
#    Open command:
#
#    Description: Open the VISA device
#                
#------------------------------------------------------------------
    def Open(self):
        self.debug_stream( "In ", self.get_name(), "::Open()")
        #    Add your own code here
        #if self.__instrument == None:
        #    self.__instrument = instrument(self.VisaName)
        #    self.set_state(tango.DevState.ON)
        self.startThread(1)


#---- Open command State Machine -----------------
    def is_Open_allowed(self):
        if self.get_state() in [tango.DevState.ON,
                                tango.DevState.FAULT]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#    Close command:
#
#    Description: Close the VISA device
#                
#------------------------------------------------------------------
    def Close(self):
        self.debug_stream( "In ", self.get_name(), "::Close()")
        #    Add your own code here
        try:
            self.__instrument.close()
            self.stopThread()
            self.set_state(tango.DevState.OFF)
            self.machineStatus()
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#---- Close command State Machine -----------------
    def is_Close_allowed(self):
        if self.get_state() in [tango.DevState.OFF]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#    Write command:
#
#    Description: Write a string to the VISA device
#                
#    argin:  DevVarCharArray    Command string
#------------------------------------------------------------------
    def Write(self, argin):
        self.debug_stream( "In ", self.get_name(), "::Write()")
        #    Add your own code here
        try:
            command = array.array('B', argin).tostring()
            #print self.VisaName+": Writing "+command
            self.__instrument.write(command)
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#---- Write command State Machine -----------------
    def is_Write_allowed(self):
        if self.get_state() in [tango.DevState.FAULT,
                                tango.DevState.OFF]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#    Read command:
#
#    Description: Read the given amount of characters.
#                
#    argin:  DevUShort    Characters to read
#    argout: DevVarCharArray    Characters readed
#------------------------------------------------------------------
    def Read(self, argin):
        self.debug_stream( "In ", self.get_name(), "::Read()")
        #    Add your own code here
        try:
            vi = self.__instrument.vi
            vpp43 = self.__instrument._vpp43
            string = vpp43.read(vi, argin)
            #print self.VisaName+": Returning "+cutlongstrings(string, 1000)
            argout = array.array('B', string).tolist()
            return argout
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()
            return ""


#---- Read command State Machine -----------------
    def is_Read_allowed(self):
        if self.get_state() in [tango.DevState.FAULT,
                                tango.DevState.OFF]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#    ReadLine command:
#
#    Description: Read data until the end
#                
#    argout: DevVarCharArray    Characters readed
#------------------------------------------------------------------
    def ReadLine(self):
        self.debug_stream( "In ", self.get_name(), "::ReadLine()")
        #    Add your own code here
        try:
            string = self.__instrument.read()
            #print self.VisaName+": Returning "+cutlongstrings(string, 1000)
            argout = array.array('B', string).tolist()
            return argout
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()
            return ""


#---- ReadLine command State Machine -----------------
    def is_ReadLine_allowed(self):
        if self.get_state() in [tango.DevState.FAULT,
                                tango.DevState.OFF]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#    ReadValues command:
#
#    Description: Perform a read command and parses the result finding the different values.
#                It uses the ValuesFormat attribute. If you want to use another format for
#                a specific answer, please, set the ValuesFormat before.
#                Possible formats are: ascii (default), singe, double
#                
#    argout: DevVarFloatArray    List of values read
#------------------------------------------------------------------
    def ReadValues(self):
        self.debug_stream("In ", self.get_name(), "::ReadValues()")
        #    Add your own code here
        try:
            argout = self.__instrument.read_values()
            #self.debug_stream(self.VisaName+": Returning "+cutlongstrings(str(argout), 1000))
            return argout
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#---- ReadValues command State Machine -----------------
    def is_ReadValues_allowed(self):
        if self.get_state() in [tango.DevState.FAULT,
                                tango.DevState.OFF]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#    Ask command:
#
#    Description: Perform a write command and return the answer from the device.
#                
#    argin:  DevVarCharArray    Command to write
#    argout: DevVarCharArray    Answer from the device
#------------------------------------------------------------------
    def Ask(self, argin):
        self.debug_stream("In ", self.get_name(), "::Ask()")
        #    Add your own code here
        try:
            command = array.array('B', argin).tostring()
            self.debug_stream(self.VisaName+": Asking for "+command)
            string = self.__instrument.ask(command)
            self.debug_stream( self.VisaName+": Returning "+string[:1000])
            argout = array.array('B', string).tolist()
            return argout
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()
            return ""


#---- Ask command State Machine -----------------
    def is_Ask_allowed(self):
        if self.get_state() in [tango.DevState.FAULT,
                                tango.DevState.OFF]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#    AskValues command:
#
#    Description: Perform a write command and return the answer from the device parsed to have
#                a list of values using the attribute ValuesFormat. If you want to use another format for
#                a specific answer, please, set the ValuesFormat before.
#                Possible formats are: ascii (default), singe, double
#                
#    argin:  DevVarCharArray    Command to write
#    argout: DevVarFloatArray    List of values
#------------------------------------------------------------------
    def AskValues(self, argin):
        self.debug_stream( "In ", self.get_name(), "::AskValues()")
        #    Add your own code here
        try:
            command = array.array('B', argin).tostring()
            #self.debug_stream( self.VisaName+": Asking for "+command+" values")
            argout = self.__instrument.ask_for_values(command)
            #self.debug_stream( self.VisaName+": Returning "+cutlongstrings(str(argout), 1000))
            return argout
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#---- AskValues command State Machine -----------------
    def is_AskValues_allowed(self):
        if self.get_state() in [tango.DevState.FAULT,
                                tango.DevState.OFF]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#    Reset command:
#
#    Description: Performs a reset to the device
#                
#------------------------------------------------------------------
    def Reset(self):
        self.debug_stream( "In ", self.get_name(), "::Reset()")
        #    Add your own code here
        try:
            self.__instrument.clear()
            self.stopThread()
            self.startThread(1)
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#---- Reset command State Machine -----------------
    def is_Reset_allowed(self):
        if self.get_state() in [tango.DevState.FAULT,
                                tango.DevState.OFF]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#    Trigger command:
#
#    Description: Send a trigger signal to the device
#                
#------------------------------------------------------------------
    def Trigger(self):
        self.debug_stream( "In ", self.get_name(), "::Trigger()")
        #    Add your own code here
        try:
            self.__instrument.clear()
        except Exception,e:
            self.set_state(tango.DevState.FAULT)
            self.machineStatus(e)
            self.__connectionEvent.set()


#---- Trigger command State Machine -----------------
    def is_Trigger_allowed(self):
        if self.get_state() in [tango.DevState.FAULT,
                                tango.DevState.OFF]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True


#==================================================================
#
#    PyVisaClass class definition
#
#==================================================================
class PyVisaClass(tango.DeviceClass):

    #    Class Properties
    class_property_list = {
        }


    #    Device Properties
    device_property_list = {
        'VisaName':
            [tango.DevString,
            "The name of the device understood by the VISA library",
            [ "SetMePlease" ] ],
        }


    #    Command definitions
    cmd_list = {
        'Open':
            [[tango.DevVoid, ""],
            [tango.DevVoid, ""]],
        'Close':
            [[tango.DevVoid, ""],
            [tango.DevVoid, ""]],
        'Write':
            [[tango.DevVarCharArray, "Command string"],
            [tango.DevVoid, ""]],
        'Read':
            [[tango.DevUShort, "Characters to read"],
            [tango.DevVarCharArray, "Characters readed"]],
        'ReadLine':
            [[tango.DevVoid, ""],
            [tango.DevVarCharArray, "Characters readed"]],
        'ReadValues':
            [[tango.DevVoid, ""],
            [tango.DevVarFloatArray, "List of values read"]],
        'Ask':
            [[tango.DevVarCharArray, "Command to write"],
            [tango.DevVarCharArray, "Answer from the device"]],
        'AskValues':
            [[tango.DevVarCharArray, "Command to write"],
            [tango.DevVarFloatArray, "List of values"]],
        'Reset':
            [[tango.DevVoid, ""],
            [tango.DevVoid, ""]],
        'Trigger':
            [[tango.DevVoid, ""],
            [tango.DevVoid, ""]],
        }


    #    Attribute definitions
    attr_list = {
        'Timeout':
            [[tango.DevFloat,
            tango.SCALAR,
            tango.READ_WRITE],
            {
                'label':"Timeout",
                'min value':0,
                'description':"Timeout in seconds for all device operations\nDefault value is 5 and you can set it to 0 for\nnon-blocking mode.\nNote that your local VISA library may round up this\nvalue heavily. I experienced this effect with my\nNational Instruments VISA implementation,\nwhich rounds off to 0, 1, 3 and 10 seconds.",
                'Memorized':"true",
            } ],
        'ChunkSize':
            [[tango.DevShort,
            tango.SCALAR,
            tango.READ_WRITE],
            {
                'label':"ChunkSize",
                'description':"Length of read data chunks in bytes\nDefault value is 20kb",
                'Memorized':"true",
            } ],
        'ValuesFormat':
            [[tango.DevString,
            tango.SCALAR,
            tango.READ_WRITE],
            {
                'label':"ValuesFormat",
                'description':"Data format for lists of read values\n+) ASCII (the default)\n+) SINGLE\n+) DOUBLE\n+) BIG_ENDIAN\n\nThis attribute is useful with the\nReadValues and AskForValues commands",
                'Memorized':"true",
            } ],
        'TermChars':
            [[tango.DevString,
            tango.SCALAR,
            tango.READ_WRITE],
            {
                'label':"TermChars",
                'description':"The termination characters for each read and write operation.\nNone (Default)\n\r (CR)\n\ n (LF)\n\nor any combination",
                'Memorized':"true",
            } ],
        'SendEnd':
            [[tango.DevBoolean,
            tango.SCALAR,
            tango.READ_WRITE],
            {
                'label':"SendEnd",
                'description':"whether to assert END after each write operation\nDefault value is True",
                'Memorized':"true",
            } ],
        'Delay':
            [[tango.DevFloat,
            tango.SCALAR,
            tango.READ_WRITE],
            {
                'label':"Delay",
                'min value':0,
                'description':"Delay time to wait after each write operation\nDefault is 0",
                'Memorized':"true",
            } ],
        }


#------------------------------------------------------------------
#    PyVisaClass Constructor
#------------------------------------------------------------------
    def __init__(self, name):
        tango.DeviceClass.__init__(self, name)
        self.set_type(name);
        print "In PyVisaClass  constructor"

#==================================================================
#
#    PyVisa class main method
#
#==================================================================
def main(*args):
    try:
        py = tango.Util(*args)
        py.add_TgClass(PyVisaClass,PyVisa,'PyVisa')

        U = tango.Util.instance()
        U.server_init()
        U.server_run()

    except tango.DevFailed,e:
        print '-------> Received a DevFailed exception:',e
    except Exception,e:
        pass

if __name__ == "__main__":
	main(sys.argv)