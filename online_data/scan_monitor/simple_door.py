import sardana.taurus.core.tango.sardana.macroserver as sms
from taurus.core.util.codecs import CodecFactory
import builtins

#sms.registerExtensions()

class simpleDoor(sms.BaseDoor):

    def __init__(self, name, **kw):

        self.queue = builtins.__dict__['queue']

        self.last_data = None

        self.call__init__(sms.BaseDoor, name, **kw)

    def recordDataReceived(self, s, t, v):

        try:
            dataRecord = sms.BaseDoor.recordDataReceived(self, s, t, v)
        except Exception as e:
            print(repr(e))
            return

        if v == None:
            return

        if dataRecord != None:

            try:
                records = self.recordData
            except Exception as e:
                print(repr(e))
                return


            # print(records)
            dec_format = records[0]
            codec = CodecFactory().getCodec(dec_format)
            records = codec.decode(records)

            try:
                self.queue.put_nowait((dataRecord, records))
            except Exception as e:
                print(repr(e))
