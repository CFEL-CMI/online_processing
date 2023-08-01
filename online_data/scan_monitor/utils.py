import PyTango
from taurus.core.util.codecs import CodecFactory
import taurus
import time

def getServerNameByClass(argin):
    '''Return a list of servers containing the specified class '''

    db = PyTango.Database()

    srvs = db.get_server_list("*").value_string

    argout = []

    for srv in srvs:
        classList = db.get_server_class_list(srv).value_string
        for clss in classList:
            if clss == argin:
                argout.append(srv)
                break
    return argout


def getDeviceNamesByClass(className):
    '''Return a list of all devices of a specified class'''

    srvs = getServerNameByClass(className)
    argout = []

    db = PyTango.Database()
    if not db:
        return None

    for srv in srvs:
        argout += db.get_device_name(srv, className).value_string

    return argout


def getMacroServerProxy():
    '''
    returns the proxy to the MacroServer
    '''
    msNames = getDeviceNamesByClass('MacroServer')
    if msNames == []:
        print("getMacroServerProxy: no MacroServer found")
        return None
    if len(msNames) > 1:
        print(f"getMacroServerProxy: more than one MacroServer {msNames}")
        return None
    try:
        mcs = taurus.Device(msNames[0])
    except Exception as e:
        print(f"getMacroServerProxy: exception from DeviceProxy {msNames[0]}")
        print(f"getMacroServerProxy {e}")
        return None

    return mcs


def getDoorProxy():
    '''
    returns the proxy to the Door
    '''

    doorName = getDeviceNamesByClass('Door')[0]

    try:
        doorDev = taurus.Device(doorName)
    except Exception as e:
        print(f"getMacroServerProxy: exception from DeviceProxy {doorName}")
        print(f"getMacroServerProxy {e}")
        return None

    return doorDev


def getMacroServerEnvironment():
    '''display the MS environment'''

    ms = getMacroServerProxy()
    if ms is None:
        return None

    dct = CodecFactory().getCodec('pickle').decode(ms.Environment)[1]['new']
    return dct


def runMacro(line):
    doorDev = getDoorProxy()
    if doorDev is None:
        print("runMacro: no door")
        return False

    doorDev.runMacro(line.split(' '))

    while doorDev.state() == PyTango.DevState.RUNNING:
        time.sleep(0.1)

    if doorDev.state() != PyTango.DevState.ON:
        raise ValueError(f"runMacro: Door state not ON, instead {doorDev.state()}")

    return True