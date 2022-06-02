# -*- coding: utf-8 -*-
"""
Subclass the QDoubleSpinBox to allow custom format strings.
"""
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import pyqtProperty
import re
import numpy as np
from si_prefix import si_format, si_parse

def _si_format(value,sig_figs=3):
    if np.abs(value)<1E-24 or np.isnan(value):
        fmt=f"{{:{sig_figs+1}.{sig_figs-1}f}}"
        return fmt.format(0.0)
    if np.abs(value)>999.9E24:
        return "+inf" if value>0 else "-inf"
    prefix_order=["y","z","a","f","p","n","u","m","","k","M","G","T","P","E","Z","Y"]
    oom=int(np.floor(np.log10(np.abs(value))))
    prefix_val=10**((oom//3)*3)
    numerical=np.round(value/prefix_val,sig_figs-1-oom%3)
    if oom%3==sig_figs-1:
        numerical=int(numerical)
    suffix=prefix_order[oom//3+8]
    return f"{numerical}{suffix}"

def _si_parse(txt):
    si_number=re.compile(r'(?P<numeric>\-?[0-9]+(\.[0-9]*)?)\s?(?P<suffix>[munpfazykMGTPEZY]?)')
    prefix_order=["y","z","a","f","p","n","u","m","","k","M","G","T","P","E","Z","Y"]
    if match:=si_number.match(txt.strip()):
        number=float(match.groupdict()["numeric"])
        prefix_oom=(prefix_order.index(match.groupdict()["suffix"])-8)*3
        return number*10**prefix_oom
    return np.nan


class FormattedDoubleSpinBox(QtWidgets.QDoubleSpinBox):

    """A Double Precision SpinBox that allows a variety of formats."""

    fmt_string=re.compile(r'\%(?P<conv>[\#0_\s\+])?(?P<length>[0-9]+)?(\.(?P<precision>[0-9]+))?(?P<format>[diouxXeEfFgGp])')
    reg_number=re.compile(r'\-?[0-9]+(\.[0-9]*)?(Ee]\-?[0-9]+)?')
    si_number=re.compile(r'\-?[0-9]+(\.[0-9]*)?\s?[munpfazykMGTPEZY]?')

    def __init__(self, *args, **kargs):
        """Capture a format keyword argument."""
        self.format=kargs.pop("format","%.3p")
        super().__init__(*args,**kargs)

    @pyqtProperty(str)
    def format(self):
        return self._format

    @format.setter
    def format(self,fmt):
        """Check the format string matches a recognised format and store."""
        if _parsed_fmt:=self.fmt_string.match(fmt):
            self._format=fmt
            self._parsed_fmt=_parsed_fmt.groupdict()
        else:
            raise ValueError(f"Unrecognised format string: {fmt}")


    def textFromValue(self, v):
        """Depending on format and prevision covert v to a formatted string."""
        if self._parsed_fmt["format"]=="p":
            precision=int(self._parsed_fmt.get("precision",2))
            return _si_format(v,sig_figs=precision)
        return self.format % v

    def valueFromText(self, text):
        """Parse the text of a value back into a value."""
        if self._parsed_fmt["format"]=="p":
            return _si_parse(text)
        return float(text)

    def validate(self, text, pos):
        """Override input validation."""
        try:
            if self.reg_number.match(text) or self.si_number.match(text):
                return (QtGui.QValidator.Acceptable, text, pos)
            return (QtGui.QValidator.Intermediate, text, pos)
        except (ValueError,TypeError):
            return (QtGui.QValidator.Intermediate, text, pos)
