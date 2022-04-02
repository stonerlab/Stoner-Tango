# -*- coding: utf-8 -*-
"""
Tango driver for a Keithley 24xx based on a SCPI device
"""
from tango.server import device_property, server_run

from stoner_tango.instr.base.SCPI import SCPI
from stoner_tango.util.decorators import command, attribute, cmd


class K24XX(SCPI):

    """Tango server class for a Keithley 24xx Source Meter."""

    scpi_attrs = [{
            "SENS": [{
                    "CURR": [{
                            "RANG": [cmd(
                                    "current_sense_range",
                                    dtype=float,
                                    descr="Range level for current measurements",
                                    label="I range",
                                    units="A",
                                    range=(0, 1.05),
                                ),{
                                    "AUTO": [cmd(
                                            "current_sense_autorange",
                                            dtype=bool,
                                            descr="Sense current autoranging",
                                            label="Autorange I?",
                                        ),{
                                            "LLIM": cmd(
                                                "current_sense_autorange_lowerlimit",
                                                dtype=float,
                                                descr="Sense current autoranging lower limit",
                                                label="Autorange I limit",
                                                units="A",
                                                range=(0, 1 - 5e-6),
                                            )
                                        },
                                    ]
                                },{
                                    "NPLC": cmd(
                                        "current_sense_nlpc",
                                        dtype=float,
                                        descr="Number ofpowerline cycles for current sensing",
                                        label="I NPLC",
                                        range=(0.01, 10.0),
                                    )
                                },
                            ]
                        }
                    ]
                }
            ]
        }
    ]


if __name__ == "__main__":
    K24XX.run_server()
