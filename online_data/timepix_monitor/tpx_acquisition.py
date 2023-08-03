import numpy as np
import pandas as pd

import asyncio

from IPython.lib import backgroundjobs as bg

from pymepix.channel.client import Client
from pymepix.channel.channel_types import ChannelDataType
import pymepix.config.load_config as cfg

def unregister_all():
    global _callback_functions_set
    callback_functions_set_copy = _callback_functions_set.copy()
    for f in callback_functions_set_copy:
        _unregister_callback(f)


def _register_callback(func):
    global _callback_functions_set
    if func in _callback_functions_set:
        return
    callback_functions_set_copy = _callback_functions_set.copy()
    for f in callback_functions_set_copy:
        if f.__name__ == func.__name__:
            _callback_functions_set.remove(f)
    _callback_functions_set.add(func)
    print(f'registered callback function: {func}')


def _unregister_callback(func):
    global _callback_functions_set
    if func in _callback_functions_set:
        _callback_functions_set.remove(func)
        print(f'unregistered callback function: {func}')


def callback(func):
    global _register_callback
    _register_callback(func)
    return func

    return wrapper


def _convert2df(data):
    if data['type'] == ChannelDataType.TOF.value:
        data['data'] = pd.DataFrame(np.vstack(data['data']).T, columns=['nr', 'x', 'y', 'tof', 'tot'])
    elif data['type'] == ChannelDataType.CENTROID.value:
        data['data'] = pd.DataFrame(np.vstack(data['data']).T,
                                    columns=['nr', 'x', 'y', 'tof', 'tot_avg', 'tot_max', 'clustersize'])
    elif data['type'] == ChannelDataType.PIXEL.value:
        data['data'] = pd.DataFrame(np.vstack(data['data']).T, columns=['x', 'y', 'toa', 'tot'])
    return data


def put_in_queue_no_wait(data):
    global _async_queue
    try:
        _async_queue.put_nowait(data)
    except:
        pass


def _main_loop():
    global _async_queue
    global _event_loop
    global _data_queue
    global _recent_data

    async_queue_half_size = int(_ASYNC_QUEUE_FULL_MAX_SIZE / 2)

    while True:

        data = _data_queue.get()

        # if DATA_FILTER is not None and data['type'] not in DATA_FILTER:
        #    continue

        data = _convert2df(data)

        if data['type'] != ChannelDataType.COMMAND.value:

            if _async_queue.qsize() <= async_queue_half_size:
                # _event_loop.call_soon_threadsafe(_async_queue.put_nowait, data) # no exception handling
                # _async_queue.put_nowait(data) #works but no notified waiting queue.get
                _event_loop.call_soon_threadsafe(put_in_queue_no_wait, data)
        else:
            _event_loop.call_soon_threadsafe(_async_queue.put_nowait, data)


async def _from_queue2callback():
    global _async_queue
    global _unregister_callback

    while True:

        data = await _async_queue.get()

        functions2unregister = []

        for f in _callback_functions_set:
            try:
                f(data)
            except Exception as e:
                functions2unregister.append(f)
                print('EXCEPTION!!! ', e)

        for f in functions2unregister:
            _unregister_callback(f)



def initialize_timepix_monitor():
    global _ASYNC_QUEUE_FULL_MAX_SIZE

    global _channel_address

    global _client
    global _data_queue
    global _jobs

    global _DATA_FILTER
    global _async_queue
    global _event_loop
    global _callback_functions_set

    if '_client' in globals():
        print('Already initialized')
        return

    _ASYNC_QUEUE_FULL_MAX_SIZE = 10

    _channel_address = tuple(cfg.default_cfg.get('tcp_channel', ['127.0.0.1', 5056]))

    _client = Client(_channel_address, None, )

    _data_queue = _client.get_queue()
    _jobs = bg.BackgroundJobManager()

    _DATA_FILTER = None
    _async_queue = asyncio.LifoQueue(maxsize=_ASYNC_QUEUE_FULL_MAX_SIZE)
    _event_loop = asyncio.get_event_loop()
    _callback_functions_set = set()

    _event_loop.create_task(_from_queue2callback())

    # _event_loop.call_soon_threadsafe(_from_queue2callback)

    _jobs.new(_main_loop)