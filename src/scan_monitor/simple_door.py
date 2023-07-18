import sardana.taurus.core.tango.sardana.macroserver as sms

class simpleDoor(sms.BaseDoor):

    def __init__( self, name, **kw):

        self.queue = builtins.__dict__['queue']

        self.call__init__( sms.BaseDoor, name, **kw)


    def recordDataReceived( self, s, t, v):

        try:
            dataRecord = sms.BaseDoor.recordDataReceived( self, s, t, v)
        except Exception as e:
            print( repr(e)
            return

        if dataRecord != None:

            try:
                self.queue.put_nowait(dataRecord)
            except Exception as e:
                print(repr( e))
