# -*- coding: utf-8 -*-
"""
Subclass the QDoubleSpinBox to allow custom format strings.
"""
from PyQt5 import QtWidgets, QtGui
import re
from si_prefix import si_format, si_parse


class FormattedDoubleSpinBox(QtWidgets.QDoubleSpinBox):

    """A Double Precision SpinBox that allows a variety of formats."""

    fmt_string=re.compile(r'\%(?P<conv>[\#0_\s\+])?(?P<length>[0-9]+)?(\.(?P<precision>[0-9]+))?(?P<format>[diouxXeEfFgGp])')

    def __init__(self, *args, **kargs):
        """Capture a format keyword argument."""
        self.format=kargs.pop("format","%.3p")
        super().__init__(*args,**kargs)

    @property
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
            return si_format(v,precision=precision)
        return self.format % v

    def valueFromText(self, text):
        """Parse the text of a value back into a value."""
        if self._parsed_fmt["format"]=="p":
            return si_parse(text)
        return float(text)

    def validate(self, text, pos):
        """Override input validation."""
        print(text,pos)
        try:
            self.valueFromText(text)
        except (ValueError,TypeError):
            return QtGui.QValidator.Intermediate
        return QtGui.QValidator.Acceptable
