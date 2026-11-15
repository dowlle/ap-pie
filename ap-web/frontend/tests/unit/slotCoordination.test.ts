import assert from 'node:assert/strict';
import test from 'node:test';
import { bkDuration, matchesCoordination } from '../../src/lib/slotCoordination.ts';

test('BK duration is compact and handles clock skew', () => {
  const since = '2026-11-15T12:00:00Z';
  const start = Date.parse(since);
  for (const [elapsed, expected] of [[-1, '<1m'], [0, '<1m'], [60_000, '1m'],
    [3_600_000, '1h'], [86_400_000, '1d']] as const) {
    assert.equal(bkDuration(since, start + elapsed), expected);
  }
});

test('BK and go mode filters compose and exclude unattached slots', () => {
  const bk = { bk_since: 'now', go_mode_since: null };
  const go = { bk_since: null, go_mode_since: 'now' };
  assert.equal(matchesCoordination(undefined, false, false), true);
  assert.equal(matchesCoordination(undefined, true, false), false);
  assert.equal(matchesCoordination(bk, true, false), true);
  assert.equal(matchesCoordination(go, true, false), false);
  assert.equal(matchesCoordination(go, false, true), true);
  assert.equal(matchesCoordination(bk, true, true), false);
  assert.equal(matchesCoordination({ ...bk, go_mode_since: 'now' }, true, true), true);
});
