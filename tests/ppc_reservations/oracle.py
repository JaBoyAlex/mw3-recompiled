# SPDX-License-Identifier: GPL-3.0-only
"""Independent allowed-state transitions; no SDK/emitter implementation imported.

Only a single aligned location is used. A valid reservation MAY lose spuriously.
Every conditional store consumes it, including failure. A successful other-context
store invalidates it even if the value is unchanged. No granule size is inferred.
"""
import random

FAMILIES = ('load', 'pair', 'none', 'consumed', 'lost', 'aba', 'isolation')
SENTINEL = 0xDEADBEEF13579BDF
MASK64 = (1 << 64) - 1


def cases(seed=0x20110360):
    if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError('seed must be uint32')
    rng = random.Random(seed)
    rows = []
    for width in (4, 8):
        mask = (1 << (width * 8)) - 1
        values = [0, 1, mask, 1 << (width * 8 - 1), 0x12345678 & mask]
        values += [rng.getrandbits(width * 8) for _ in range(7)]
        for indexed in (False, True):
            for n, initial in enumerate(values):
                for so in (0, 1):
                    # Equal/opposite SO controls separate reservation failures from
                    # failure to copy XER.SO on either conditional-store outcome.
                    cr = 0xE | (so if n % 2 else 1 - so)
                    new = initial ^ mask
                    load = lambda c: dict(op='load', ctx=c, value=0)
                    store = lambda c, v: dict(op='store', ctx=c, value=v)
                    plans = {
                        'load': [load(0)],
                        'pair': [load(0), store(0, new)],
                        'none': [store(0, new)],
                        'consumed': [load(0), store(0, initial), store(0, new)],
                        'lost': [load(0), load(1), store(1, new), store(0, initial), store(0, initial)],
                        'aba': [load(0), load(1), store(1, new), load(1), store(1, initial), store(0, new)],
                        'isolation': [load(0), store(1, new), store(0, new)],
                    }
                    for family, steps in plans.items():
                        rows.append(dict(id=f'{family}-{width}-{int(indexed)}-{n}-{so}', family=family,
                            width=width, indexed=indexed, initial=initial, so=so, cr=cr, steps=steps))
    return rows


def validate_cases(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1024:
        raise ValueError('bounded case list required')
    ids = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id', 'family', 'width', 'indexed', 'initial', 'so', 'cr', 'steps'} or
                type(row['id']) is not str or not 1 <= len(row['id']) <= 64 or row['id'] in ids or
                row['family'] not in FAMILIES or type(row['width']) is not int or row['width'] not in (4, 8) or
                type(row['indexed']) is not bool or type(row['so']) is not int or row['so'] not in (0, 1) or
                type(row['cr']) is not int or not 0 <= row['cr'] <= 15 or
                type(row['initial']) is not int or not 0 <= row['initial'] < 1 << (row['width'] * 8)):
            raise ValueError('invalid case')
        ids.add(row['id'])
        if not isinstance(row['steps'], list) or not 1 <= len(row['steps']) <= 8:
            raise ValueError('bounded steps required')
        for step in row['steps']:
            if (not isinstance(step, dict) or set(step) != {'op', 'ctx', 'value'} or
                    step['op'] not in ('load', 'store') or type(step['ctx']) is not int or step['ctx'] not in (0, 1) or
                    type(step['value']) is not int or not 0 <= step['value'] < 1 << (row['width'] * 8)):
                raise ValueError('invalid step')


def evaluate(case, observed):
    """Validate architectural outcomes, accepting a failing SC with a valid reserve.

    An observed success chooses the success branch only when a reservation is
    valid. Invalid successes cannot bless changed memory. Premises for lost/ABA
    require both-context stores to succeed; otherwise coverage is INCONCLUSIVE.
    """
    if len(observed) != len(case['steps']):
        raise ValueError('incomplete steps')
    memory = case['initial']
    reserved = [False, False]
    registers = [SENTINEL, SENTINEL]
    cr = [case['cr'], case['cr']]
    failures = []
    progress = []
    for i, (step, actual) in enumerate(zip(case['steps'], observed)):
        ctx = step['ctx']
        checks = {}
        if step['op'] == 'load':
            registers[ctx] = memory
            reserved[ctx] = True
        else:
            succeeded = bool(actual['cr'] & 2)
            allowed = reserved[ctx]
            checks['reservation'] = not succeeded or allowed
            cr[ctx] = (2 if succeeded and allowed else 0) | case['so']
            reserved[ctx] = False
            if succeeded and allowed:
                memory = step['value']
                reserved[1 - ctx] = False
            if ctx == 1 and case['family'] in ('lost', 'aba'):
                progress.append(succeeded and allowed)
        checks.update(load=actual['r3'] == registers[ctx], cr=actual['cr'] == cr[ctx],
                      memory=actual['memory'] == memory, so=actual['so'] == case['so'],
                      guards=actual['guards'], preserved=actual['preserved'])
        failures.extend(f'{i}:{name}' for name, valid in checks.items() if not valid)
    status = 'FAIL' if failures else 'INCONCLUSIVE' if progress and not all(progress) else 'PASS'
    return dict(id=case['id'], family=case['family'], status=status, failures=failures)
