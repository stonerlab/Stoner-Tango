from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtProperty, pyqtSignal

from scipy.signal import sawtooth
import pyqtgraph as pg
import numpy as np
import sys

class Waveform(QtWidgets.QWidget):

    valueChanged=pyqtSignal()

    def __init__(self):
        super().__init__() # Call the inherited classes __init__ method
        uic.loadUi('waveform_generator.ui', self) # Load the .ui file
        for part in ["amplitude","offset","points","periods","phase"]:
            part=getattr(self,part)
            part.valueChanged.connect(self.redraw)
        self.waveform.currentIndexChanged.connect(self.redraw)
        self.waveform.currentIndexChanged.connect(self._sort_visibility)
        self._value=np.empty(0)
        self.redraw()
        self.setLayout(self.main_layout)
        self.show() # Show the GUI

    @pyqtProperty(np.ndarray)
    def value(self):
        """Get our waveform from the widget."""

    @value.setter
    def value(self, data):
        """Emit a signal when we change the data."""
        self._value=data
        self.valueChanged.emit()


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
        periods=self.periods.value()
        t=np.linspace(0,points,points)
        if not hasattr(self,func):
            y=np.zeros_like(t)
        else:
            y=getattr(self,func)()
            self.display.clear()
        self.display.plot(t,y)
        self.display.plot(t,np.zeros_like(t),pen=pg.mkPen({"color":"#EEEE00","width":2.0}))
        self.display.getPlotItem().hideAxis('bottom')
        self.display.getPlotItem().hideAxis('left')
        self.value=y

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
