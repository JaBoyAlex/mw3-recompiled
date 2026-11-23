# SPDX-License-Identifier: GPL-3.0-only
"""Independent byte serialization of the explicitly declared default SDK test policy.

This is not a retail/console oracle. Unknown retail flags and alternate modes remain
unverified. These expectations do not import SDK headers or call SDK helper code.
"""
import struct

SERVICES = (
    ('VdQueryVideoMode', 0x1ca),
    ('VdGetCurrentDisplayInformation', 0x1ba),
    ('VdGetCurrentDisplayGamma', 0x1b9),
    ('VdQueryVideoFlags', 0x1c9),
)
SIZE = 0x20000


def plan(seed, reverse=False):
    offsets = [0x10, 0x80, 0x120, 0xffb0]
    for _ in range(4):
        seed = (1664525 * seed + 1013904223) & 0xffffffff
        offsets.append(0x200 + ((seed >> 8) % ((SIZE - 0x400) // 16)) * 16)
    rows = [(service, offset) for _ in range(4) for offset in offsets for service in range(4)]
    return list(reversed(rows)) if reverse else rows


def expected(service, output_offset=16):
    if type(service) is not int or not 0 <= service < 4: raise ValueError('unknown service')
    data = bytearray([0xa7] * 128)
    at = output_offset
    if service == 0:
        # Explicit selected-SDK default: 1280x720 progressive/60Hz, flags 1/1.
        payload = struct.pack('>5If6I', 1280, 720, 0, 1, 1, 60.0, 1, 0x4a, 1, 0, 0, 0)
        data[at:at+48] = payload
    elif service == 1:
        payload = bytearray(88)
        struct.pack_into('>HH', payload, 0, 1280, 720)
        struct.pack_into('>II', payload, 16, 1280, 720)  # source rectangle x2/y2
        struct.pack_into('>III', payload, 24, 1280, 720, 1)
        struct.pack_into('>I', payload, 48, 1)  # horizontal filter type
        struct.pack_into('>6Hf', payload, 64, 320, 180, 320, 180, 1280, 720, 60.0)
        struct.pack_into('>H', payload, 86, 1280)
        data[at:at+88] = payload
    elif service == 2:
        data[at:at+4] = struct.pack('>I', 2)
        data[80:84] = struct.pack('>f', 2.22222233)
    return bytes(data)


def check_row(row, service, offset):
    """Return observed deviations; never transform a missing/unsafe record into PASS."""
    required = {'service', 'offset', 'bytes', 'r3', 'before', 'after', 'external_canary', 'elapsed_ns'}
    if type(row) is not dict or set(row) != required: raise ValueError('invalid observation fields')
    if (type(row['service']) is not int or row['service'] != service or type(row['offset']) is not int or row['offset'] != offset or
            type(row['r3']) is not int or not 0 <= row['r3'] < 2**64 or type(row['elapsed_ns']) is not int or not 0 <= row['elapsed_ns'] <= 5_000_000_000 or
            type(row['external_canary']) is not bool or type(row['bytes']) is not str or len(row['bytes']) != 256):
        raise ValueError('invalid observation types or identity')
    for name in ('before', 'after'):
        if (type(row[name]) is not list or len(row[name]) != 21 or
                any(type(v) is not int or not 0 <= v < 2**64 for v in row[name])):
            raise ValueError('invalid preserved-register observation')
    if row['before'][0] % 16 or not row['before'][2]: raise ValueError('not an initialized guest context')
    try: observed = bytes.fromhex(row['bytes'])
    except ValueError as error: raise ValueError('invalid byte observation') from error
    if len(observed) != 128: raise ValueError('incomplete byte observation')
    failures = []
    if observed != expected(service): failures.append('output-extent/endian/canary')
    if not row['external_canary']: failures.append('external-canary')
    if row['before'] != row['after']: failures.append('nonvolatile-gpr')
    if service == 3 and row['r3'] != 3: failures.append('flag-return')
    return failures
