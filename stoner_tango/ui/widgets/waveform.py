from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtProperty, pyqtSignal, pyqtSlot

from scipy.signal import sawtooth
import pyqtgraph as pg
import numpy as np
import sys

class BaseWaveform(QtWidgets.QWidget):

    valueChanged=pyqtSignal()

    def __init__(self):
        super().__init__() # Call the inherited classes __init__ method
        try:
            uic.loadUi('waveform_generator.ui', self) # Load the .ui file
        except SystemError:
            pass

class Waveform(BaseWaveform):

    """Subclass the Base so we can add properties."""

    def __init__(self,*args, **kargs):
        super().__init__(*args,**kargs)
        for part in ["amplitude","offset","points","periods","phase"]:
            part=getattr(self,part)
            part.valueChanged.connect(self.redraw)
        self.waveform.currentIndexChanged.connect(self.redraw)
        self.waveform.currentIndexChanged.connect(self._sort_visibility)
        self._value=np.empty(0)
        self._x_axis=True
        self._show_current_pos=False
        self._position=-1
        self.redraw()
        self.setLayout(self.main_layout)
        self.show() # Show the GUI

    @pyqtProperty(bool)
    def show_position(self):
        """Show the current position on the display."""
        return self._show_current_pos

    @show_position.setter
    def show_position(self,value):
        self._show_current_pos=bool(value)

    @pyqtProperty(int)
    def position(self):
        """Return the current position marker location.

        This is 0<=position<=value.size if value.size is not 0, otherwise -1."""
        if self.value.size>0:
            return max(0,min(self._position, self.value.size))
        return -1

    @position.setter
    def position(self, value):
        value=int(value)
        if not 0<=value<self.value.size:
            raise ValueError(f"{value} is oitside the range of posints in the waveform (0-{self.value.size-1})")
        self._position=value


    @pyqtProperty(bool)
    def x_axis(self):
        """Control whether the x_axis is displayed or not."""
        return self._x_axis

    @x_axis.setter
    def x_axis(self,value):
        self._x_axis=bool(value)

    @pyqtProperty(np.ndarray)
    def value(self):
        """Get our waveform from the widget."""
        return self._value

    @value.setter
    def value(self, data):
        """Emit a signal when we change the data."""
        self._value=data
        self.valueChanged.emit()

    @pyqtProperty(str)
    def unit(self):
        """The unit suffix string."""
        return self.amplitude.suffix()

    @unit.setter
    def unit(self, value):
        value=str(value)
        self.amplitude.setSuffix(value)
        self.offset.setSuffix(value)

    @pyqtSlot(int)
    def upadtePosition(self,value):
        """Slot for updating the current position marker."""
        self.position=value

    def _timebase(self):
        """Calculate the time values to feed into the waveform generation functions."""
        points=self.points.value()
        periods=self.periods.value()
        phase=self.phase.value()
        start_t=(phase+90)*np.pi/180
        end_t=start_t+periods*2*np.pi
        return np.linspace(start_t,end_t,points,endpoint=False)

    def _sort_visibility(self):
        """IF the waveform type changes we might need to reset some labels and visibility."""
        waveform=self.waveform.currentText()
        for k in ["periods","periods_label","phase","phase_label"]:
            getattr(self,k).setHidden(waveform=="Ramp")
        self.amplitude_label.setText("End" if waveform=="Ramp" else "Amplitude")
        self.offset_label.setText("Start" if waveform=="Ramp" else "Offset")

    def closeEvent(self, event):
        """Catch the close event."""
        print("Closed")
        event.accept()

    def redraw(self):
        func=self.waveform.currentText().lower().replace("^","_")
        points=self.points.value()
        t=np.linspace(0,points,points)
        if not hasattr(self,func):
            y=np.zeros_like(t)
        else:
            y=getattr(self,func)()
            self.display.clear()
        self.display.plot(t,y)
        if self._x_axis:
            self.display.plot(t,np.zeros_like(t),pen=pg.mkPen({"color":"#EEEE00","width":2.0}))
        if self._show_current_pos:
            self.display.plot(x=[t[self.position]],y=[self.value[self.position]], pen=None, symbol='o')
        self.display.getPlotItem().hideAxis('bottom')
        self.display.getPlotItem().hideAxis('left')
        self.value=y

    def ramp(self):
        """Simple ramp function."""
        finish=self.amplitude.value()
        start=self.offset.value()
        return np.linspace(start,finish,int(self.points.value()),endpoint=True)


    def triangle(self):
        """Make a triangle wave."""
        ammplitude=self.amplitude.value()
        offset=self.offset.value()
        return sawtooth(self._timebase(),width=0.5)*ammplitude+offset

    def sine(self):
        """Implement a sine wave."""
        ammplitude=self.amplitude.value()
        offset=self.offset.value()
        return np.sin(self._timebase()-np.pi/2)*ammplitude+offset

    def square(self):
        """Implement a square wave function."""
        ammplitude=self.amplitude.value()
        offset=self.offset.value()
        y0=sawtooth(self._timebase()+1E-6,width=0.5)
        return np.sign(y0)*ammplitude+offset

    def x_2(self):
        """Implement a parabolic shaped oscillation."""
        ammplitude=self.amplitude.value()
        offset=self.offset.value()
        y0=sawtooth(self._timebase(),width=0.5)
        return np.sign(y0)*y0**2*ammplitude+offset

    def x_3(self):
        """Implement a parabolic shaped oscillation."""
        ammplitude=self.amplitude.value()
        offset=self.offset.value()
        y0=sawtooth(self._timebase(),width=0.5)
        return y0**3*ammplitude+offset

    def x_4(self):
        """Implement a parabolic shaped oscillation."""
        ammplitude=self.amplitude.value()
        offset=self.offset.value()
        y0=sawtooth(self._timebase(),width=0.5)
        return np.sign(y0)*y0**4*ammplitude+offset

if __name__=="__main__":
        if not QtWidgets.QApplication.instance():
            app = QtWidgets.QApplication(sys.argv)
            window = Waveform()
            app.exec_()
        else:
            window = Waveform()
        window.unit="A"
        window.show_position=True
        window.position=10
