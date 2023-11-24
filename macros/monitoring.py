##############################################################################

"""macro module for data monitoring"""

__all__ = ["ctn"]


__docformat__ = 'restructuredtext'

import datetime
import os
import re
import time

import numpy as np
from taurus import Device
from taurus.console.table import Table
import PyTango
from PyTango import DevState

from sardana.macroserver.macro import Macro, macro, Type, ViewOption, \
    iMacro, Hookable
from sardana.macroserver.msexception import StopException, UnknownEnv
from sardana.macroserver.scan.scandata import Record
from sardana.macroserver.macro import Optional

from sardana.macroserver.macros.standard import _ct
from sardana.macroserver.macros.standard import _value_to_repr

##########################################################################


class ctn(Macro, Hookable, _ct):
    """Count for the specified time on the measurement group
       or experimental channel given as second argument, 
       as a second parameter is the number of counts,
       (if not given the active measurement group is used)"""

    hints = {'allowsHooks': ('pre-acq', 'post-acq')}
    param_def = [
        ['integ_time', Type.Float, 1.0, 'Integration time'],
        ['repeats', Type.Integer, 1, 'number of repetitions'],
        ['countable_elem', Type.Countable, Optional,
         'Countable element e.g. MeasurementGroup or ExpChannel']
    ]



    def run(self, integ_time, repeats, countable_elem):

        from sardana.sardanaevent import EventType

        if countable_elem is None:
            try:
                self.countable_elem_name = self.getEnv('ActiveMntGrp')
            except UnknownEnv:
                msg = ('No countable element. Use macro parameter or set'
                   ' ActiveMntGrp environment variable.')
                raise RuntimeError(msg)
        else:
            self.countable_elem_name = countable_elem.name
        self.countable_elem = self.getObj(self.countable_elem_name)
        if self.countable_elem is None:
            msg = ('ActiveMntGrp is referencing a nonexistent countable element.')
            raise RuntimeError(msg)

        # integration time has to be accessible from with in the hooks
        self.integ_time = integ_time

        for i in range(repeats):

            self.debug("Counting for %s sec", integ_time)
            self.outputDate()
            self.output('')
            self.flushOutput()

            for preAcqHook in self.getHooks('pre-acq'):
                preAcqHook()

            try:
                state, data = self.countable_elem.count(integ_time)
            except Exception:
                self.dump_information(self._getElements())
                raise
            if state != DevState.ON:
                self.dump_information(self._getElements())
                raise ValueError("Acquisition ended with {}".format(
                    state.name.capitalize()))

            for postAcqHook in self.getHooks('post-acq'):
                postAcqHook()

            names, counts = [], []
            if self.countable_elem.type == Type.MeasurementGroup:
                meas_grp = self.countable_elem
                for ch_info in meas_grp.getChannelsEnabledInfo():
                    names.append('  %s' % ch_info.label)
                    ch_data = data.get(ch_info.full_name)
                    counts.append(_value_to_repr(ch_data))
            else:
                channel = self.countable_elem
                names.append("  %s" % channel.name)
                counts.append(_value_to_repr(data))
                # to be compatible with measurement group count
                data = {channel.full_name: data}

            self.setData(Record(data))

            self.getDoorObj().fire_event(EventType("recorddata", priority=1),
                                         ('utf8_json', {'type': 'record_single',
                                                        'data': {'timestamp': time.time()}, 'macro_id': self.getID() })
                                         )

            table = Table([counts], row_head_str=names, row_head_fmt='%*s',
                          col_sep='  =  ')
            for line in table.genOutput():
                self.output(line)

