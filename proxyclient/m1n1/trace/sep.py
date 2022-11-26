from m1n1.trace.asc import BaseASCTracer, EP, DIR, msg
from m1n1.hw.sep import *
import struct
from collections import namedtuple

BaseASCTracer = BaseASCTracer._reloadcls()

SEPOSApps = {}

shmem_base = None
shmem_objects = None

class SEPTracer(EP):
    BASE_MESSAGE = SEPMessage
    ObjEntry = namedtuple("ObjEntry", "name sz offset data")

    def debug_shell(self):
        self.hv.run_shell(locals())

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.sram_addr = None
        self.state.verbose = 1

    def ioread(self, addr, len, hex_str=False):
        try:
            if hex_str:
                return self.tracer.ioread(addr, len).hex()
            else:
                return self.tracer.ioread(addr, len)
        except:
            return None

    def GetChannelObjEntries(self):
        addr = shmem_base
        entries = {}
        while True:
            obj_entry = self.tracer.ioread(addr, 16)
            name, sz, offset = struct.unpack("<4sII", obj_entry[0:12])
            name = name.decode()
            if name == "llun":
                break
            else:
                data = self.tracer.ioread(shmem_base + offset, sz)
                entries[name] = self.ObjEntry._make((name, sz, offset, data))
            addr += 16
        return entries

    def GetChannelObjEntry(self, obj_name):
        addr = shmem_base
        while True:
            obj_entry = self.tracer.ioread(addr, 16)
            name, sz, offset = struct.unpack("<4sII", obj_entry[0:12])
            name = name.decode()
            if name == "llun":
                break
            elif name == obj_name:
                return self.ObjEntry._make((name, sz, offset))
            addr += 16

    def dump_shmem(self):
        global shmem_objects
        null = b'\x00'
        if shmem_base:
            objs = self.GetChannelObjEntries()
            if shmem_objects:
                for obj in objs:
                    if shmem_objects[obj] != objs[obj]:
                        #self.log(f"SHMEM {obj} = {objs[obj].data}")
                        self.log(f"SHMEM {obj} ({hex(objs[obj].offset)}) changed = ({objs[obj].data.strip(null)})")
            else:
                for obj in objs:
                    self.log(f"SHMEM {obj} ({hex(objs[obj].offset)}) = ({objs[obj].data.strip(null)})")
                    #self.log(f"SHMEM {obj} = {hex(objs[obj].offset)}")
            shmem_objects = objs

    @msg(None, DIR.TX, SEPMessage)
    def TXMsg(self, msg):
        self.dump_shmem()
        self.log(f">UNK {msg}")
        #self.debug_shell()
        return True

    @msg(None, DIR.RX, SEPMessage)
    def RXMsg(self, msg):
        self.dump_shmem()
        self.log(f"<UNK {msg}")
        #self.debug_shell()
        return True

class SEPCntlTracer(SEPTracer):
    @msg(None, DIR.TX, SEPMessage)
    def TXMsg(self, msg):
        self.dump_shmem()
        self.log(f">cntl {msg}")
        addr = msg.DATA << 0xC
        self.log(f">cntl bytes: {self.ioread(addr, 64, hex_str=True)}")
        self.debug_shell()
        return True

    @msg(None, DIR.RX, SEPMessage)
    def RXMsg(self, msg):
        self.dump_shmem()
        self.log(f"<cntl {msg}")
        addr = msg.DATA << 0xC
        self.log(f"<cntl bytes: {self.ioread(addr, 64, hex_str=True)}")
        self.debug_shell()
        return True

class SEPROMTracer(SEPTracer):
    @msg(BootRomMsg.BOOT_IMG4, DIR.TX, SEPMessage)
    def BootIMG4(self, msg):
        addr = msg.DATA << 0xC
        self.log(f"SEPFW address: {hex(addr)}")
        self.log(f"Some SEPFW bytes: {self.tracer.ioread(addr, 64)}")
        return True

    @msg(BootRomMsg.SET_SHMEM, DIR.TX, SEPMessage)
    def SetShmem(self, msg):
        global shmem_base
        self.log(f">MSG={BootRomMsg(msg.TYPE).name} {msg}")
        shmem_base = msg.DATA << 0xC
        self.log(f"SEP shared memory: {hex(shmem_base)}")
        self.debug_shell()
        return True

    @msg(None, DIR.TX, SEPMessage)
    def TXMsg(self, msg):
        try:
            self.log(f">UNK MSG={BootRomMsg(msg.TYPE).name} {msg}")
        except ValueError:
            self.log(f"Unknown SEP message - {msg}")
        return True

    @msg(None, DIR.RX, SEPMessage)
    def RXMsg(self, msg):
        try:
            self.log(f"<UNK STATUS={BootRomStatus(msg.TYPE).name} {msg}")
        except ValueError:
            self.log(f"Unknown SEP message - {msg}")
        return True

class SEPOSUnkFD(SEPTracer):
    APP_ENDPOINTS = {
        "cntl": SEPCntlTracer
    }

    @msg(UnkFDMsg.REPORT_APP_STATUS, DIR.RX, SEPMessage)
    def ReportAppStatus(self, msg):
        app_id = msg.PARAM
        app_status = msg.DATA
        SEPOSApps[app_id]["status"] = app_status
        self.log(f"SEPOS App: {SEPOSApps[app_id]['name']} (Endpoint: {hex(app_id)}), Status: {hex(SEPOSApps[app_id]['status'])}")
        return True

    @msg(UnkFDMsg.REPORT_APP_NAME, DIR.RX, SEPMessage)
    def ReportAppName(self, msg):
        app_ep = msg.PARAM
        app_name = struct.pack('>Q', msg.DATA).decode().strip('\x00')
        self.log(f"SEPOS App: {app_name} (Endpoint: {hex(app_ep)})")
        if app_name in self.APP_ENDPOINTS:
            self.log(f"Registering app endpoint: {app_name}")
            self.tracer.set_endpoint(app_ep, self.APP_ENDPOINTS[app_name])
        SEPOSApps.setdefault(app_ep, {"name": app_name})
        return True

class SEPTracer(BaseASCTracer):
    ENDPOINTS = {
        0x0E: SEPTracer,
        0x13: SEPTracer,
        0xFF: SEPROMTracer,
        0xFE: SEPROMTracer,
        0xFD: SEPOSUnkFD
    }

    def handle_msg(self, direction, r0, r1):
        self.log(f"r1: {r1}")
        r0 = SEPMessage(r0.value)
        r1 = r0
        super().handle_msg(direction, r0, r1)

    def start(self, dart=None):
        super().start(dart=dart)
        tracer = self
        self.dart = dart
