# SPDX-License-Identifier: GPL-3.0-only
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ppc_reservations import oracle


def observation(r3=oracle.SENTINEL, cr=1, memory=0, so=1):
    return dict(r3=r3, cr=cr, memory=memory, so=so, guards=True, preserved=True, ns=100)


def case(steps, initial=0, family='pair'):
    return dict(id='original', family=family, width=4, indexed=False, initial=initial, so=1, cr=0xE, steps=steps)


def load(ctx=0):
    return dict(op='load', ctx=ctx, value=0)


def store(value, ctx=0):
    return dict(op='store', ctx=ctx, value=value)


class ReservationOracleTests(unittest.TestCase):
    def test_seeded_inventory_is_bounded_reproducible_and_held_out(self):
        rows = oracle.cases()
        oracle.validate_cases(rows)
        self.assertEqual(len(rows), 672)
        self.assertEqual(rows, oracle.cases())
        self.assertNotEqual(rows, oracle.cases(1))
        self.assertEqual({r['family'] for r in rows}, set(oracle.FAMILIES))
        for seed in (-1, True, 1 << 32):
            with self.assertRaises(ValueError): oracle.cases(seed)

    def test_valid_pair_can_succeed_or_fail_spuriously(self):
        row = case([load(), store(7)], initial=3)
        first = observation(r3=3, cr=0xE, memory=3)
        for second in (observation(r3=3, cr=3, memory=7), observation(r3=3, cr=1, memory=3)):
            self.assertEqual(oracle.evaluate(row, [first, second])['status'], 'PASS')

    def test_no_reservation_cannot_store_even_when_old_value_matches(self):
        row = case([store(7)], family='none')
        self.assertEqual(oracle.evaluate(row, [observation()])['status'], 'PASS')
        result = oracle.evaluate(row, [observation(cr=3, memory=7)])
        self.assertEqual(result['failures'], ['0:reservation', '0:cr', '0:memory'])

    def test_success_and_failure_both_consume_reservation(self):
        row = case([load(), store(0), store(7)], family='consumed')
        first = observation(r3=0, cr=0xE)
        for cr in (1, 3):
            good = [first, observation(r3=0, cr=cr), observation(r3=0)]
            self.assertEqual(oracle.evaluate(row, good)['status'], 'PASS')
            good[-1] = observation(r3=0, cr=3, memory=7)
            self.assertIn('2:reservation', oracle.evaluate(row, good)['failures'])

    def test_intervening_same_value_write_and_aba_invalidate_other_context(self):
        # A reads0; B reads0, stores1, reads1, stores0; A must fail despite equal bits.
        row = case([load(), load(1), store(1, 1), load(1), store(0, 1), store(7)], family='aba')
        trace = [observation(r3=0, cr=0xE), observation(r3=0, cr=0xE),
            observation(r3=0, cr=3, memory=1), observation(r3=1, cr=3, memory=1),
            observation(r3=1, cr=3), observation(r3=0)]
        self.assertEqual(oracle.evaluate(row, trace)['status'], 'PASS')
        trace[-1] = observation(r3=0, cr=3, memory=7)
        self.assertIn('5:reservation', oracle.evaluate(row, trace)['failures'])
        same = case([load(), load(1), store(0, 1), store(7)])
        self.assertIn('3:reservation', oracle.evaluate(same, [observation(r3=0, cr=0xE),
            observation(r3=0, cr=0xE), observation(r3=0, cr=3), observation(r3=0, cr=3, memory=7)])['failures'])

    def test_unexercised_interference_is_inconclusive_not_compatibility_pass(self):
        row = case([load(), load(1), store(1, 1), store(0), store(0)], family='lost')
        trace = [observation(r3=0, cr=0xE), observation(r3=0, cr=0xE), observation(r3=0),
                 observation(r3=0), observation(r3=0)]
        self.assertEqual(oracle.evaluate(row, trace)['status'], 'INCONCLUSIVE')

    def test_so_flags_memory_and_preservation_are_independent_checks(self):
        row = case([store(7)], family='none')
        for key, value in [('cr', 0), ('so', 0), ('memory', 7), ('guards', False), ('preserved', False)]:
            actual = observation(); actual[key] = value
            self.assertEqual(oracle.evaluate(row, [actual])['status'], 'FAIL', key)

    def test_invalid_case_inputs_and_partial_trace_refused(self):
        rows = oracle.cases()[:1]
        for bad in ([], rows * 2, [dict(rows[0], width=True)], [dict(rows[0], initial=-1)],
                    [dict(rows[0], steps=[dict(op='store', ctx=2, value=0)])]):
            with self.assertRaises(ValueError): oracle.validate_cases(bad)
        with self.assertRaises(ValueError): oracle.evaluate(rows[0], [])


if __name__ == '__main__': unittest.main()
