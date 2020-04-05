import time
import struct
from binascii import hexlify

from pyBusPirateLite import *
from crccheck.crc import (Crc7, Crc16)

class SDSPI:
    def __init__(self):
        self.spi = SPI()
        self.spi.pins = 0
        time.sleep(0.2)
        self.spi.pins = SPI.PIN_POWER | SPI.PIN_CS
        self.spi.config = SPI.CFG_CLK_EDGE | SPI.CFG_PUSH_PULL
        self.spi.speed = '250kHz'

    def __enter__(self):
        self.spi.cs = True

    def __exit__(self, type, value, traceback):
        self.spi.cs = False

    def cmd(self, cmd, arg, rlen=0, data=None):
        cmdb = struct.pack('>BI', cmd | 0x40, arg)
        crc7 = Crc7.calc(cmdb)
        txb = cmdb + bytes([(crc7 << 1) | 1])

        with self:
            self.spi.transfer(txb)
            rxb = self._read_response(rlen+1)
            status = rxb[0]
            rxb = rxb[1:]

            error = status & 0xfe != 0
            print("CMD%d: %s -> %x %s" % (cmd, txb.hex(), status, rxb.hex()))

            if not error and data:
                crc16 = Crc16.calcbytes(data)
                data_start = 0xfe
                ind = self.spi.transfer([data_start])
                print("data start: %x" % data_start)
                print("data read: %s" % ind.hex())
                while len(data) > 0:
                    chunk = data[0:16]
                    data = data[16:]
                    ind = self.spi.transfer(chunk)
                    print("data write: %s" % chunk.hex())
                    print("data read: %s" % ind.hex())

                ind = self.spi.transfer(crc16)
                print("data crc: %s" % crc16.hex())
                print("data read: %s" % ind.hex())

                data_resp = self._read_response(4)[0]
                self._wait_busy()

                if data_resp & 0b00011111 != 0b00000101:
                    raise RuntimeError('data write error %x' % data_resp)

        if rlen > 0:
            return status, rxb
        else:
            return status

    def _read_response(self, rlen, wait=8):
        rxb = b''
        while len(rxb) < rlen:
            b = self.spi.transfer(b'\xff')
            print('rx %s' % b.hex())
            if b[0] != 0xff or len(rxb) > 0:
                rxb += b
            else:
                wait = wait - 1
                if wait < 0:
                    return b'0xff'

        return rxb

    def _wait_busy(self):
        while True:
            b = self.spi.transfer(b'\xff')
            if b[0] != 0:
                return

    def acmd(self, *args, **kwargs):
        self.cmd(55, 0)
        return self.cmd(*args, **kwargs)

    def init(self):
        for _ in range(16):
            status = self.cmd(0, 0)
            if status == 1:
                break
            continue
        if status & 0xfe != 0:
            raise RuntimeError('cannot initialize card')

        status, reply = self.cmd(8, 0x1a, 4)
        if status & 0xfe != 0 or reply != b'\0\0\0\x1a':
            raise RuntimeError('bad interface condition')

        status, ocr_b = self.cmd(58, 0, 4)

        while _ in range(1024):
            status = self.acmd(41, 0x40000000)
            if status & 1 == 0:
                break

        status, ocr_b = self.cmd(58, 0, 4)

    def lock_unlock(self, cmd, opw, npw=b''):
        # cmd:
        # 0 = unlock
        # 1 = set password
        # 2 = clear password
        # 4 = lock card now
        # 8 = erase card
        pw = opw + npw
        pwblock = struct.pack('>BB', cmd, len(pw)) + pw
        status = self.cmd(16, len(pwblock))
        if status & 0xfe != 0:
            return status
        self.cmd(42, 0, data=pwblock)
        return self.acmd(13, 0, 1)
