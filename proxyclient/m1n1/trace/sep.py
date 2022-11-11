from m1n1.trace.asc import ASCTracer, EP, DIR, msg
from m1n1.hw.sep import *

ASCTracer = ASCTracer._reloadcls()


class SEPTracer(EP):
    BASE_MESSAGE = SEPMessage

    def debug_shell(self):
        self.hv.run_shell(locals())

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.sram_addr = None
        self.state.verbose = 1

    @msg(None, DIR.TX, SEPMessage)
    def TXMsg(self, msg):
        self.log(f">UNK {msg}")
        self.debug_shell()

    @msg(None, DIR.RX, SEPMessage)
    def RXMsg(self, msg):
        self.log(f"<UNK {msg}")
        self.debug_shell()

class SEPROMTracer(SEPTracer):
    BASE_MESSAGE = SEPMessage

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.sram_addr = None
        self.state.verbose = 1

    @msg(BootRomMsg.BOOT_IMG4, DIR.TX, SEPMessage)
    def BootIMG4(self, msg):
        addr = msg.DATA << 0xC
        self.log(f"SEPFW address: {hex(addr)}")
        self.log(f"Some SEPFW bytes: {self.tracer.ioread(addr, 64)}")

    @msg(BootRomMsg.SET_SHMEM, DIR.TX, SEPMessage)
    def SetShmem(self, msg):
        addr = msg.DATA << 0xC
        self.shmem = addr
        self.log(f"SEP shared memory: {hex(self.shmem)}")

    @msg(None, DIR.TX, SEPMessage)
    def TXMsg(self, msg):
        try:
            self.log(f">UNK MSG={BootRomMsg(msg.TYPE).name}, TAG={msg.TAG}, PARAM={msg.PARAM}, DATA={msg.DATA}")
        except ValueError:
            self.log(f"Unknown SEP message - {msg}")

    @msg(None, DIR.RX, SEPMessage)
    def RXMsg(self, msg):
        try:
            self.log(f"<UNK STATUS={BootRomStatus(msg.TYPE).name}, TAG={msg.TAG}, PARAM={msg.PARAM}, DATA={msg.DATA}")
        except ValueError:
            self.log(f"Unknown SEP message - {msg}")

class SEPTracer(ASCTracer):
    ENDPOINTS = {
        0x00: SEPTracer,
        0xFF: SEPROMTracer,
        0xFE: SEPROMTracer
    }

    def handle_msg(self, direction, r0, r1):
        r0 = SEPMessage(r0.value)
        r1 = r0
        super().handle_msg(direction, r0, r1)

    def start(self, dart=None):
        super().start(dart=dart)
        tracer = self
        self.dart = dart
