import { load } from "js-yaml";
import type { ParsedTemplate } from "../api";
import { CORE_OPTIONS } from "./coreOptions";

/**
 * FEAT-43 / gap 1: read a YAML back into builder form values.
 *
 * The builder was a one-way door - every path produced a document and
 * nothing read one back, so editing your own file meant raw text even if you
 * had built it with the form. This is the other direction.
 *
 * Anything the schema does not declare is returned in `unknown` rather than
 * dropped, so a caller can decide honestly: a file carrying plando or
 * triggers belongs in the editor, not in a form that would silently discard
 * half of it.
 */
export interface ImportedYaml {
  playerName: string;
  game: string;
  values: Record<string, unknown>;
  coreValues: Record<string, unknown>;
  /** Keys in the game section the schema has no option for. */
  unknown: string[];
  /** Root-level keys beyond the ones the builder itself emits. */
  extraRootKeys: string[];
}

const OWN_ROOT_KEYS = new Set(["name", "game", "description", "requires"]);

export function importYaml(
  text: string,
  template: ParsedTemplate | null,
): ImportedYaml | null {
  let doc: unknown;
  try {
    doc = load(text);
  } catch {
    return null;
  }
  if (!doc || typeof doc !== "object") return null;
  const root = doc as Record<string, unknown>;

  const game = typeof root.game === "string" ? root.game : template?.game ?? "";
  const section = (root[game] ?? {}) as Record<string, unknown>;
  const coreNames = new Set(CORE_OPTIONS.map((o) => o.name));
  const known = new Set((template?.options ?? []).map((o) => o.name));

  const values: Record<string, unknown> = {};
  const coreValues: Record<string, unknown> = {};
  const unknown: string[] = [];

  if (section && typeof section === "object") {
    for (const [k, v] of Object.entries(section)) {
      if (coreNames.has(k)) coreValues[k] = v;
      else if (known.has(k)) values[k] = v;
      else unknown.push(k);
    }
  }

  return {
    playerName: typeof root.name === "string" ? root.name : "Player1",
    game,
    values,
    coreValues,
    unknown,
    extraRootKeys: Object.keys(root).filter(
      (k) => !OWN_ROOT_KEYS.has(k) && k !== game,
    ),
  };
}
