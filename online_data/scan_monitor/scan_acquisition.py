import asyncio
import copy
import sardana.taurus.core.tango.sardana.macroserver as sms
from sardana.macroserver.scan.scandata import Record as SardanaRecord

from .utils import *
from .simple_door import simpleDoor

_ASYNC_QUEUE_FULL_MAX_SIZE = 8

from IPython.lib import backgroundjobs as bg

import queue, builtins


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


def get_formatted(data):
    ''' the function is intended to get rid of dublicates
    and add record data to metadata during a scan'''

    global _last_record_data

    recordData, records = data

    # after counter macro we may get only one Record object on both recordData and records
    if type(recordData[1]) == SardanaRecord:
        res = ('', dict())
        res[1]['type'] = 'record_single'
        res[1]['records'] = records[1]
        return res
 
    # detect if we got only last records in recordData instead of scan info
    only_last_records = False
    if all([isinstance(it, int) for it in recordData[1].keys()]):  # got last records
        only_last_records = True


    if recordData[1] == _last_record_data:
        return None

    if only_last_records:
        if _last_record_data == list(recordData[1].keys()):
            return None
        _last_record_data = list(recordData[1].keys())
    else:
        _last_record_data = copy.copy(recordData[1])

    if only_last_records:
        res = ('', dict())
        res[1]['type'] = 'records'
        res[1]['records'] = records[1]
        return res

    if 'type' in recordData[1].keys():
        recordData[1]['records'] = records[1]
        return recordData[1]


def _main_loop():
    global _async_queue
    global _event_loop
    global _data_queue

    while True:

        data = _data_queue.get()

        # print('before formatting data: ', data)

        data = get_formatted(data)

        # print(' after formatting data: ', data)

        if data != None:
            if _async_queue.qsize() <= _ASYNC_QUEUE_FULL_MAX_SIZE:
                _event_loop.call_soon_threadsafe(put_in_queue_no_wait, data)


def put_in_queue_no_wait(data):
    global _async_queue
    try:
        _async_queue.put_nowait(data)
    except:
        pass


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



def initialize_scan_monitor():
    if not 'JsonRecorder' in getMacroServerEnvironment().keys():
        runMacro('senv JsonRecorder True')

    import taurus
    factory = taurus.Factory()
    factory.registerDeviceClass('Door', simpleDoor)

    global simpledoor

    global _ASYNC_QUEUE_FULL_MAX_SIZE

    global _data_queue

    global _jobs
    global _event_loop
    global _async_queue
    global _callback_functions_set

    global _last_record_data

    builtins.__dict__['queue'] = queue.Queue()

    _last_record_data = None

    sms.registerExtensions()

    simpledoor = simpleDoor((getDeviceNamesByClass('Door')[0]))

    #_ASYNC_QUEUE_FULL_MAX_SIZE = 8

    _data_queue = simpledoor.queue

    _jobs = bg.BackgroundJobManager()
    _event_loop = asyncio.get_event_loop()
    _async_queue = asyncio.LifoQueue(maxsize=_ASYNC_QUEUE_FULL_MAX_SIZE)
    _callback_functions_set = set()

    _event_loop.create_task(_from_queue2callback())

    _jobs.new(_main_loop)