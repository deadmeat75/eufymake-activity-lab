"""Eufy printer wire protocol, adapted from masto/eufy-ink (Unlicense).

Original protocol credits:
https://charliex2.wordpress.com/2026/03/06/eufy/
https://github.com/Django1982/ankerctl_go_remake/
"""
from __future__ import annotations
import dataclasses
import struct
import uuid
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

BROKERS = {
    "US": "make-mqtt.ankermake.com",
    "CA": "make-mqtt.ankermake.com",
    "MX": "make-mqtt.ankermake.com",
    "EU": "make-mqtt-eu.ankermake.com",
    "GB": "make-mqtt-eu.ankermake.com",
    "DE": "make-mqtt-eu.ankermake.com",
    "FR": "make-mqtt-eu.ankermake.com",
}

CBC_IV = b"3DPrintAnkerMake"

def _pkcs7_pad(data: bytes) -> bytes:
    p = PKCS7(128).padder()
    return p.update(data) + p.finalize()

def _pkcs7_unpad(data: bytes) -> bytes:
    u = PKCS7(128).unpadder()
    return u.update(data) + u.finalize()

def _xor(data: bytes) -> int:
    x = 0
    for b in data:
        x ^= b
    return x

@dataclasses.dataclass
class Frame:
    magic: str  # "MA" or "MB"
    size: int
    header_size: int  # 24 (M5=6 / M5=1) or 64 (M5=2); +2 for 'MB'
    m5: int  # header variant byte: 1=M5C, 2=M5 (app), 6=UV printer broadcast
    packet_type: int  # 0xC0 = single, 0xC1..C3 = fragmented
    packet_num: int
    timestamp: int  # unix seconds; populated when M5=2 (and in practice for M5=6 too)
    ciphertext: bytes
    checksum_ok: bool
    raw: bytes

def parse_frame(wire: bytes) -> Frame:
    if len(wire) < 12:
        raise ValueError(f"frame too short: {len(wire)} bytes")
    magic = wire[:2]
    if magic == b"MA":
        size = int.from_bytes(wire[2:4], "little")
        size_bytes = 2
    elif magic == b"MB":
        size = int.from_bytes(wire[2:6], "little")
        size_bytes = 4
    else:
        raise ValueError(f"bad magic {magic!r}")
    if size != len(wire):
        raise ValueError(f"size field {size} != wire len {len(wire)}")

    m5 = wire[2 + size_bytes + 2]  # byte index [6] for MA, [8] for MB
    packet_type = wire[2 + size_bytes + 5]
    packet_num = int.from_bytes(wire[2 + size_bytes + 6 : 2 + size_bytes + 8], "little")
    timestamp = int.from_bytes(wire[2 + size_bytes + 8 : 2 + size_bytes + 12], "little")

    # Header length depends on the M5 variant:
    #   M5 = 2       -> 64 bytes (3D printer/desktop-app "M5" format)
    #   M5 = 1 or 6  -> 24 bytes ("M5C" / UV printer broadcast format)
    header_len = (64 if m5 == 2 else 24) + (size_bytes - 2)

    if len(wire) < header_len + 17:
        raise ValueError("truncated encrypted frame")
    return Frame(
        magic=magic.decode(),
        size=size,
        header_size=header_len,
        m5=m5,
        packet_type=packet_type,
        packet_num=packet_num,
        timestamp=timestamp,
        ciphertext=wire[header_len:-1],
        checksum_ok=_xor(wire[:-1]) == wire[-1],
        raw=wire,
    )

def decrypt(key: bytes, ciphertext: bytes) -> bytes:
    dec = Cipher(algorithms.AES(key), modes.CBC(CBC_IV)).decryptor()
    padded = dec.update(ciphertext) + dec.finalize()
    return _pkcs7_unpad(padded)

def build_app_frame(key: bytes, plaintext: bytes) -> bytes:
    """Build an 'MA' (or 'MB') frame in the format the desktop app sends.

    This is the 64-byte "M5" variant with a random DeviceGUID in the 37-byte
    C-string slot. The printer will only respond to commands wrapped this
    way; the shorter 24-byte variant (which the printer itself emits) is
    silently dropped. Matches the default packet layout in
    ankerctl_go_remake/internal/mqtt/protocol/packet.go.
    """
    enc = Cipher(algorithms.AES(key), modes.CBC(CBC_IV)).encryptor()
    ct = enc.update(_pkcs7_pad(plaintext)) + enc.finalize()
    header_len = 64
    total = header_len + len(ct) + 1
    if total <= 0xFFFF:
        magic = b"MA"
        size_field = struct.pack("<H", total)
    else:
        magic = b"MB"
        size_field = struct.pack("<I", total + 2)  # +2 for the wider size field

    device_guid = str(uuid.uuid4()).encode("ascii").ljust(37, b"\x00")[:37]

    head = (
        magic
        + size_field
        + bytes(
            [
                0x05,  # M3
                0x01,  # M4
                0x02,  # M5 = 2 (app-to-printer flavour)
                0x05,  # M6
                0x46,  # M7 ('F')
                0xC0,  # packet_type = single
            ]
        )
        + struct.pack("<H", 0)  # packet_num
        + struct.pack("<I", 0)  # time (the desktop app sends 0)
        + device_guid
        + b"\x00" * 11  # padding
    )
    frame = head + ct
    return frame + bytes([_xor(frame)])

def subscribe_topics(sn: str, uid: str) -> list[str]:
    # The broker's ACL accepts these specific topics but refuses '#'/'+'
    # wildcards, so we have to enumerate them.
    return [
        f"/phone/maker/{sn}/notice",
        f"/phone/maker/{sn}/command/reply",
        f"/phone/maker/{sn}/query/reply",
        f"/phone/maker/{sn}/change_notice",
        f"/phone/user/{uid}/change_notice",
    ]
