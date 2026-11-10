/**
 * Number fields for a counter that sits inside a nested OptionDict.
 *
 * The parser only tags a flat OptionCounter as `dict_kind: "counter"`, so an
 * option such as CTR's `item_pool` (`base: relics: platinum: 6`) used to fall
 * back to a free-text YAML box. A spec here names the game, the option, the
 * path to the counter inside it and the fields to show. The builder renders
 * one number input per field and writes only that counter; every other entry
 * of the option stays exactly as the user typed it.
 */

export interface NestedCounterField {
  key: string;
  label: string;
  /** Value written when the field has no number yet. */
  default: number;
}

export interface NestedCounterSpec {
  apworld: string;
  option: string;
  /** Keys leading from the option value to the counter mapping. */
  path: string[];
  title: string;
  hint: string;
  min: number;
  max: number;
  fields: NestedCounterField[];
}

export const NESTED_COUNTER_SPECS: NestedCounterSpec[] = [
  {
    apworld: "ctr",
    option: "item_pool",
    path: ["base", "relics"],
    title: "Relic counts",
    hint:
      "Base Relics in the pool. Platinum Time Trial checks exist only when Platinum is above 0. " +
      "Everything else in Item Pool stays in the YAML box below.",
    min: 0,
    max: 18,
    fields: [
      { key: "sapphire", label: "Sapphire Relics", default: 18 },
      { key: "gold", label: "Gold Relics", default: 18 },
      { key: "platinum", label: "Platinum Relics", default: 0 },
    ],
  },
];

export function findNestedCounterSpec(
  apworld: string | undefined,
  option: string,
): NestedCounterSpec | undefined {
  return NESTED_COUNTER_SPECS.find((s) => s.apworld === apworld && s.option === option);
}

type Mapping = Record<string, unknown>;

const isMapping = (v: unknown): v is Mapping =>
  typeof v === "object" && v !== null && !Array.isArray(v);

/** Mapping at the spec path, `{}` when the path is absent, or null when an
 * entry on the way is not a mapping (then the fields stay hidden so no typed
 * value gets overwritten). */
export function counterAt(spec: NestedCounterSpec, value: unknown): Mapping | null {
  let node: unknown = value ?? {};
  for (const key of spec.path) {
    if (!isMapping(node)) return null;
    node = node[key] ?? {};
  }
  return isMapping(node) ? node : null;
}

/** Number to show for a field: the typed integer in range, else the default. */
export function fieldValue(spec: NestedCounterSpec, value: unknown, field: NestedCounterField): number {
  const raw = counterAt(spec, value)?.[field.key];
  return typeof raw === "number" && Number.isInteger(raw) && raw >= spec.min && raw <= spec.max
    ? raw
    : field.default;
}

/** True when the field holds something the number input cannot show. */
export function fieldIsCustom(spec: NestedCounterSpec, value: unknown, field: NestedCounterField): boolean {
  const raw = counterAt(spec, value)?.[field.key];
  return raw !== undefined && fieldValue(spec, value, field) !== raw;
}

/** New option value with one field set. All fields of the counter are written
 * so a partial `relics` mapping never leaves the others to a guess (a typed value the inputs cannot show is kept as typed); siblings
 * of the counter and unrelated entries are kept. Returns null when the path
 * is blocked by a non-mapping. */
export function withFieldValue(
  spec: NestedCounterSpec,
  value: unknown,
  field: NestedCounterField,
  next: number,
): Mapping | null {
  const current = counterAt(spec, value);
  if (!current) return null;
  const clamped = Math.min(spec.max, Math.max(spec.min, Math.trunc(Number.isFinite(next) ? next : field.default)));
  const counter: Mapping = { ...current };
  for (const f of spec.fields) {
    if (f.key === field.key) counter[f.key] = clamped;
    else if (current[f.key] === undefined) counter[f.key] = f.default;
    // else: keep whatever the user typed, even if the number input cannot show it
  }
  const build = (node: unknown, depth: number): Mapping => {
    if (depth === spec.path.length) return counter;
    const m: Mapping = isMapping(node) ? node : {};
    return { ...m, [spec.path[depth]]: build(m[spec.path[depth]], depth + 1) };
  };
  return build(value, 0);
}
