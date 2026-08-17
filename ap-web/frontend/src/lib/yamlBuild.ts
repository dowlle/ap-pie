import { dump } from "js-yaml";
import type { ParsedTemplate, TemplateOption } from "../api";

/**
 * FEAT-38: build a submittable Archipelago YAML from builder form values.
 *
 * js-yaml owns all scalar quoting/escaping (player names like "true" or
 * "why: not", option strings with quotes, unicode) - the class of bug the
 * old hand-rolled string-concat emitter had. Values are emitted as a
 * single fixed value per option (no weights) per the FEAT-38 v1 scope.
 */
export function buildYamlContent(input: {
  playerName: string;
  /** YAML `game:` string (the index game_name). */
  game: string;
  /** APWorld version for `requires.game.<game>` - the room's pin (room
   *  flow) or the version the user picked on /apworlds (index flow).
   *  Empty string omits the requires block. */
  worldVersion: string;
  template: ParsedTemplate;
  /** Minimum Archipelago version this apworld was built against, from the
   *  derived schema. Emitted as `requires.version`. */
  apVersion?: string;
  values: Record<string, unknown>;
  /** Archipelago's own options (see lib/coreOptions). Only keys the user
   *  actually set are present; anything left on "game default" is absent
   *  and stays absent from the document, so the game's own default wins. */
  coreValues?: Record<string, unknown>;
  coreOptions?: TemplateOption[];
}): string {
  const {
    playerName, game, worldVersion, template, values,
    coreValues = {}, coreOptions = [], apVersion,
  } = input;

  const doc: Record<string, unknown> = {
    name: playerName,
    description: `${game} - created with the ap-pie.com builder`,
    game,
  };
  if (worldVersion) {
    // `requires.game` pins the apworld; `requires.version` states the
    // minimum generator this file expects (Generate.py:539-545). Emitting
    // both means a host on an older Archipelago is told so at generation
    // time instead of hitting a confusing option error.
    const requires: Record<string, unknown> = { game: { [game]: worldVersion } };
    if (apVersion) requires.version = apVersion;
    doc.requires = requires;
  }

  const gameSection: Record<string, unknown> = {};
  // Core options first, mirroring where Archipelago's own templates put
  // them. They live inside the game section: CommonOptions keys are
  // accepted there, and keeping every option in one block is what a
  // reader expects.
  for (const opt of coreOptions) {
    const picked = coreValues[opt.name];
    if (picked === undefined || picked === "") continue;
    gameSection[opt.name] = normalizeValue(opt, picked);
  }
  for (const opt of template.options) {
    gameSection[opt.name] = normalizeValue(opt, values[opt.name]);
  }
  doc[game] = gameSection;

  return dump(doc, {
    // Option values are plain data; refs/anchors would only confuse the
    // AP generator and human readers.
    noRefs: true,
    // Don't wrap long description strings mid-scalar.
    lineWidth: -1,
    // Keep insertion order (name/description/game/requires, then options
    // in schema order) instead of alphabetical.
    sortKeys: false,
  });
}

/**
 * Archipelago resolves these strings at generation time instead of storing a
 * fixed value (`Options.py:25-56`, plus `Range.from_text`, `Choice.from_text`
 * and `Toggle.from_text`):
 *
 *   random                          any valid value, uniformly
 *   random-low / -middle / -high    weighted towards that end of a range
 *   random-range-<min>-<max>        uniform inside a sub-range
 *   random-range-<bias>-<min>-<max> the same, weighted
 *
 * They stay plain strings in the YAML even for numeric options, so the
 * emitter passes them through untouched rather than coercing to a number.
 */
export function isRandomValue(v: unknown): v is string {
  return typeof v === "string" && /^random(-|$)/.test(v);
}

/** Coerce a form value into the shape the option expects, falling back to
 *  the schema default when the user never touched the control. */
function normalizeValue(opt: TemplateOption, raw: unknown): unknown {
  const val = raw === undefined ? opt.default : raw;

  // Every option type accepts "random"; ranges accept the weighted and
  // sub-range forms too. Emit verbatim whatever the type.
  if (isRandomValue(val)) return val;

  switch (opt.type) {
    case "toggle":
      return !!val;
    case "range": {
      const n = typeof val === "number" ? val : Number(val);
      return Number.isFinite(n) ? n : opt.default;
    }
    case "list":
      if (Array.isArray(val)) return val;
      if (typeof val === "string") {
        return val.split(",").map((s) => s.trim()).filter(Boolean);
      }
      return [];
    case "dict": {
      if (typeof val === "string") {
        // The generic dict control is a "key: value" textarea; parse lines
        // into an object, numbers as numbers.
        const out: Record<string, unknown> = {};
        for (const line of val.split("\n")) {
          const idx = line.indexOf(":");
          if (idx <= 0) continue;
          const k = line.slice(0, idx).trim();
          const v = line.slice(idx + 1).trim();
          if (!k) continue;
          const n = Number(v);
          out[k] = v !== "" && Number.isFinite(n) ? n : v;
        }
        return out;
      }
      return typeof val === "object" && val !== null ? val : {};
    }
    default:
      // choice / text - string scalar; js-yaml quotes as needed.
      return val === null || val === undefined ? "" : String(val);
  }
}

/** Client-side download of the built YAML as a file. */
export function downloadYaml(yamlContent: string, playerName: string, game: string) {
  const safe = (s: string) => s.replace(/[^\w.-]+/g, "_").replace(/^_+|_+$/g, "") || "player";
  const blob = new Blob([yamlContent], { type: "text/yaml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${safe(playerName)}-${safe(game)}.yaml`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
