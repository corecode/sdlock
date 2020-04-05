# Lock SD card for RNS 315

RNS 315 appears to expect a locked SD card, with the password derived
from the CID.  Given the unencrypted nature of SD card communication,
we can simply lock a card with a bogus password and then sniff the
communication, which will reveal the expected password.

The code in sdlock.py will allow manipulation of the SD card password
settings.

```
import binascii
import sdlock

pw = binascii.unhexlify(expected_passwd)
c = sdlock.SDSPI()
c.init()
c.lock_unlock(1, pw)
print(c.acmd(13, 0, 1)) # poll extended status (7.3.2.3 Format R2)
```
