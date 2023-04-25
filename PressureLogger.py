#!/usr/bin/env python
# coding: utf-8

# In[ ]:


TANGO_GAUGE_DEV = 'tango://cfeld-pcx39081.desy.de:10000/Test/maxigaugedevice/1'
LOG_DATA_PATH = '/home/cfelcmi/pressure_log_data'
START_SERVER_COMMAND = '/home/cfelcmi/.local/bin/maxigaugedevice eCOMO &'
GAUGE_DEVICE_NAME = 'maxigaugedevice'

DATA_SIZE_LIMIT = 86400
CHUNK_SIZE = 28800

SERVE_PORT = 5007

gauge_names = ['gauge1','gauge2','gauge3','gauge4','gauge5','gauge6',]


# In[ ]:


import os
import numpy as np
import time
import queue
import taurus
import os.path
from IPython.lib import backgroundjobs as bg

import pandas as pd
from bokeh.plotting import figure
from bokeh.models import DatetimeTickFormatter
from holoviews.streams import Buffer, Pipe
import holoviews as hv
import hvplot.pandas 

import logging

from datetime import datetime

import param

import panel as pn

import asyncio


# In[ ]:


hv.extension('bokeh')
#pn.extension(sizing_mode="stretch_width")

gauge = taurus.Device(TANGO_GAUGE_DEV)

jobs = bg.BackgroundJobManager()

data_queue = queue.Queue(5)

loop = asyncio.new_event_loop()


# In[ ]:


def get_pressure_at(gauge, gaugeNr):
    pressure = getattr(gauge, f'gauge{gaugeNr}Value')
    return pressure


# In[ ]:





# In[ ]:


gauges_2plot = gauge_names
time_window_size = 16*3600
time_rolling = 0

multiply_factor_dict = {'h':3600, 'm':60}

gauges_checkbox_group = pn.widgets.CheckBoxGroup(
    name='Checkbox Group', value=gauge_names, options=gauge_names,
    inline=False)

radio_group = pn.widgets.RadioButtonGroup(
    name='Time window', options=['5m', '15m', '1h', '4h', '16h'], value='16h',  button_type='success')

def update_checkbox_var(event):
    global gauges_2plot
    gauges_2plot = event.new
    
def update_timewindow_var(event):
    global time_window_size
    global time_rolling
    time_window_size = int(event.new[:-1])*multiply_factor_dict[event.new[-1]]
    time_rolling = 0

gauges_checkbox_group.param.watch(update_checkbox_var, 'value')
radio_group.param.watch(update_timewindow_var, 'value')


# In[ ]:





# In[ ]:


pipe = Pipe(data=pd.DataFrame({'time': [], 'gauge1': [], 'gauge2': [], 'gauge3': [], 'gauge4': [], 
                               'gauge5': [], 'gauge6': []}))

xformatter=DatetimeTickFormatter( days="%d %H:%M:%S",  hours="%d %H:%M:%S",)
#                                         minutes="%d %H:%M:%S",)

def user_page(): 
    
    app_bar = pn.Row(
        pn.pane.Markdown(f"## Pressure at {TANGO_GAUGE_DEV}", style={"color": "white"}, width=900, sizing_mode="fixed", margin=(10,5,10,15)), 
        pn.Spacer(),
        background="blue",
    )
    
    def timeseries(data):    
        global gauges_2plot
        if len(gauges_2plot) == 1:
            #for some reason minimal number of elements in y list must be 2
            return data.hvplot.line(x='time', y=gauges_2plot+gauges_2plot, value_label='Presure [mBar]', 
                                          xformatter=xformatter).opts(logy=False, height=600, width=800,)
        else:
            return data.hvplot.line(x='time', y=gauges_2plot, value_label='Presure [mBar]', 
                                          xformatter=xformatter).opts(logy=True, height=600, width=800,)        
    try:
        dmap = hv.DynamicMap(timeseries, streams=[pipe]).opts(bgcolor='black',).opts(bgcolor='black',)
    except:
        return pn.Column(app_bar, pn.Row(gauges_checkbox_group, pn.Column(radio_group)))
    return pn.Column(app_bar, pn.Row(gauges_checkbox_group, pn.Column(dmap, radio_group)))

#pn.Column(app_bar, pn.Row(gauges_checkbox_group, pn.Column(dmap, radio_group)))

#pn.serve(user_page, port=SERVE_PORT)


# In[ ]:





# In[ ]:


def update_figure(data_array):
    global time_window_size
    global time_rolling
    
    data2plot = data_array[max(0,len(data_array)-time_window_size):]

    slice_factor = len(data2plot)//2000
    if slice_factor > 1:
        residual = len(data2plot)%slice_factor
        time_rolling_residual = time_rolling%slice_factor
        
        if time_window_size == len(data2plot):
            data2plot = data2plot[slice_factor - time_rolling_residual:len(data2plot)\
                                  -time_rolling_residual - residual]
            time_rolling = time_rolling + 1
        else:
            data2plot = data2plot[:len(data2plot) - residual]
            

        data2plot = data2plot.reshape(np.shape(data2plot)[0]//slice_factor, slice_factor,\
                                      np.shape(data2plot)[1])
        
        data2plot = np.mean(data2plot, axis=1)

    df = pd.DataFrame(data2plot, columns = ['time', 'gauge1','gauge2','gauge3','gauge4','gauge5','gauge6',])
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    
    
    pipe.send(df) 


# In[ ]:


class PressureLogger:
    
    def __init__(self, prefix='pressure', coarsity_factor=4,\
                 data_size_limit = 86400, chunksize = 28800, path=LOG_DATA_PATH ):
        
        self.data_array = np.zeros((data_size_limit, 7), dtype=float)
        self.prefix = prefix
        self.entry_index = 0
        self.data_size_limit = data_size_limit
        self.chunksize = chunksize # corresponds to file size
        self.current_file = None
        self.load_data()
        self.data_path = path
        
            
    
    def push_entry(self, entry):
        
        #print('got: ', entry)
        
        if self.entry_index >= self.data_size_limit:
            self._shift_left(self.chunksize)
        
        if self.entry_index%self.chunksize == 0:
            self.current_file = f'{self.prefix}1_{str(datetime.fromtimestamp(entry[0]))}.dat'
            # back conversion: datetime.strptime(datetime_str,  '%Y-%m-%d %H:%M:%S.%f')
            open(os.path.join(self.data_path, self.current_file), "x")
        
        with open(os.path.join(self.data_path, self.current_file), "ab") as f:            
            np.savetxt(f, [np.asarray(entry)],\
                       delimiter=',') 
            f.write(b"\n")
            
        self.data_array[self.entry_index] = entry
        
        self.entry_index += 1
        

            
    def get_recent_data(self, num=-1):
        if num<0:
            return self.data_array[0:self.entry_index]
        else:
            return self.data_array[max(0, self.entry_index-num):self.entry_index]
    
    def load_historical_data(self):
        pass            
            
            
    def _shift_left(self, num):
        arr_shape = np.shape(self.data_array)
        assert(num<arr_shape[0])
        cpy_arr = np.empty_like(self.data_array)
        cpy_arr[0:arr_shape[0]-num,:] = self.data_array[num:arr_shape[0],:]
        self.data_array = cpy_arr
        self.entry_index -= num
            
                
    def load_data(self):
        pass
    
    def get_data_in_range(self, limit1, limit2):
        pass
        
pressure_logger = PressureLogger(data_size_limit = DATA_SIZE_LIMIT, chunksize = CHUNK_SIZE)


# In[ ]:


def main_loop():
    while True:
        data_entry = data_queue.get()
        if data_entry == None:
            break
        pressure_logger.push_entry(data_entry)
        try:
            update_figure(pressure_logger.get_recent_data())
        except:
            pass


# In[ ]:


def loop_get_pressurevalues(gauge):
    while True:
        try:
            vals = [get_pressure_at(gauge, i) for i in range(1,7)]
        except:
            proccount = os.popen("ps -Af").read().count(GAUGE_DEVICE_NAME)
            if proccount == 0:
                os.system(START_SERVER_COMMAND) 
            time.sleep(30)
            
            continue

            
        vals = [datetime.now().timestamp()] + vals
        
        data_queue.put_nowait(vals)
        fraction2wait = 1.0 - datetime.now().timestamp()%1
        time.sleep(fraction2wait)


# In[ ]:


jobs.new(main_loop)
jobs.new(loop_get_pressurevalues, gauge)
print('jobs started')


# In[ ]:


print(jobs.status())


# In[ ]:


pn.serve(user_page, port=SERVE_PORT)


# In[ ]:


"""
start_time = datetime.now().timestamp()
for i in range(9000):
    #current_time = datetime.now().timestamp()
    current_time = start_time + i*10
    tdiff = current_time - start_time
    if tdiff < 1e-12:
        tdiff = 1e-12
    data_queue.put([current_time , tdiff*0.1,tdiff*0.3,tdiff*0.5,tdiff*0.7,tdiff*0.9,tdiff*1.1])
    time.sleep(0.1)
"""


# In[ ]:




