import assert from 'node:assert/strict';
import test from 'node:test';
import {
  counterAt, fieldIsCustom, fieldValue, findNestedCounterSpec, withFieldValue,
} from '../../src/lib/nestedCounters.ts';

const spec = findNestedCounterSpec('ctr', 'item_pool')!;
const [sapphire, gold, platinum] = spec.fields;

test('only CTR item_pool has a spec', () => {
  assert.ok(spec);
  assert.equal(findNestedCounterSpec('ctr', 'goal'), undefined);
  assert.equal(findNestedCounterSpec('refunct', 'item_pool'), undefined);
  assert.equal(findNestedCounterSpec(undefined, 'item_pool'), undefined);
});

test('defaults are 18, 18, 0 for an empty pool', () => {
  assert.deepEqual([sapphire, gold, platinum].map((f) => fieldValue(spec, {}, f)), [18, 18, 0]);
  assert.deepEqual([sapphire, gold, platinum].map((f) => fieldValue(spec, undefined, f)), [18, 18, 0]);
});

test('setting Platinum writes the base relics with all three tiers', () => {
  assert.deepEqual(withFieldValue(spec, {}, platinum, 6), {
    base: { relics: { sapphire: 18, gold: 18, platinum: 6 } },
  });
});

test('other item_pool entries and sibling keys are kept', () => {
  const typed = {
    base: { relics: { gold: 10, extra_key: 1 }, tokens: { red: 4 } },
    extra: { relics: { platinum: 2 } },
    gems: 3,
  };
  const out = withFieldValue(spec, typed, platinum, 5)!;
  assert.deepEqual(out, {
    base: { relics: { gold: 10, extra_key: 1, sapphire: 18, platinum: 5 }, tokens: { red: 4 } },
    extra: { relics: { platinum: 2 } },
    gems: 3,
  });
  assert.deepEqual(typed.base.relics, { gold: 10, extra_key: 1 }); // input not mutated
});

test('typed values show in the fields', () => {
  const v = { base: { relics: { sapphire: 3, gold: 4, platinum: 18 } } };
  assert.deepEqual([sapphire, gold, platinum].map((f) => fieldValue(spec, v, f)), [3, 4, 18]);
});

test('values are clamped to 0..18', () => {
  const hi = withFieldValue(spec, {}, platinum, 99)! as any;
  const lo = withFieldValue(spec, {}, platinum, -4)! as any;
  assert.equal(hi.base.relics.platinum, 18);
  assert.equal(lo.base.relics.platinum, 0);
});

test('a non-mapping on the path hides the fields instead of overwriting', () => {
  const blocked = { base: 'random' };
  assert.equal(counterAt(spec, blocked), null);
  assert.equal(withFieldValue(spec, blocked, platinum, 4), null);
});

test('an unshowable typed value is flagged and keeps its text until edited', () => {
  const v = { base: { relics: { platinum: 'random' } } };
  assert.equal(fieldIsCustom(spec, v, platinum), true);
  assert.equal(fieldIsCustom(spec, v, gold), false);
  assert.equal(fieldValue(spec, v, platinum), 0);
});
