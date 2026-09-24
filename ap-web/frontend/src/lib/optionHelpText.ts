/**
 * Turn an APWorld option docstring into Markdown for the YAML Builder.
 *
 * Authors hard-wrap docstrings at 75 to 120 characters for their source
 * files and the YAML template. MarkdownText renders every single newline
 * as a line break (remark-breaks), so a wrapped docstring showed as ragged
 * lines in the narrow help column. This joins those soft-wrapped lines into
 * paragraphs and keeps the line breaks that carry meaning:
 *
 *  - blank lines (paragraph breaks)
 *  - list items (`-`, `*`, `+`, `•`, `1.`, `1)`)
 *  - the line after a short one: a line much shorter than the longest line
 *    in the text was ended on purpose (markerless lists such as trap names)
 *  - "Label: text" and "VALUE - text" lines, common ways to describe
 *    choice values
 *  - the line after one that ends with a colon
 *  - a line wholly in parentheses, or a "(" line after one ending in ")"
 *  - indented lines, unless they continue a list item at its text column
 *  - headings, quotes, tables, rules, banner lines and fenced code
 *
 * reStructuredText literal blocks (an indented block after a line ending in
 * `::`) and indented blocks after an "Example:" style line become fenced
 * code blocks, so the builder can show them instead of hiding them. The
 * trailing `::` becomes `:`.
 *
 * Pure string function with no DOM access, so it can be unit tested.
 */

const LIST_ITEM = /^([-*•]|\d{1,3}[.)])\s+\S/;
// "+ " starts a list only after a blank line or another "+ " item; inside a
// paragraph it is usually wrapped arithmetic ("... milestones\n+ dexsanity").
const PLUS_ITEM = /^\+\s+\S/;
const FENCE = /^(`{3,}|~{3,})/;
const RULE = /^([-=~_*^#])\1{2,}\s*$/;
/** "-- SECTION ------" style banner lines end in a run of rule characters. */
const BANNER_END = /([-=~_*#])\1{3,}$/;
const STRUCTURAL = /^(#{1,6}\s|>|\|)/;
const LABEL = /^([*_`'"]{0,2}[\p{L}\p{N}][^:\n]{0,40}?):[*_`'"]{0,2}(\s|$)/u;
// "MUST_WIN - text" and "Vanilla - text": one identifier, then a dash.
const DASH_LABEL = /^[*_`'"]{0,2}(?:\p{Lu}|[\p{L}\p{N}]*_)[\p{L}\p{N}_'"`*]{0,30}\s[-–]\s/u;
const EXAMPLE_INTRO = /\b(example|examples|e\.g\.|for instance)\b/i;

type Kind = "none" | "blank" | "text" | "list" | "code" | "other";

function indentOf(line: string): number {
  return line.length - line.trimStart().length;
}

/**
 * "Vanilla: items stay put" style lines. A capitalised, quoted or numeric
 * label of up to four words, or a single lowercase word such as `open:`.
 * A lowercase phrase before a colon is usually a wrapped sentence.
 */
function isLabelLine(content: string, previousContent: string): boolean {
  if (previousContent.endsWith(",")) return false;
  if (DASH_LABEL.test(content)) return true;
  const match = LABEL.exec(content);
  if (!match) return false;
  const label = match[1].replace(/[*_`'"]/g, "").trim();
  const words = label.split(/\s+/).length;
  if (label.length === 0 || words > 4) return false;
  const marked = /^[*_`'"]/.test(match[1]) || /^[\p{Lu}\p{N}]/u.test(label);
  return marked || words === 1;
}

/** Rewrite a trailing reST `::` marker. Returns null when nothing is left. */
function stripLiteralMarker(line: string): string | null {
  const trimmed = line.trimEnd();
  if (trimmed.trim() === "::") return null;
  if (trimmed.endsWith(" ::")) return trimmed.slice(0, -3);
  return trimmed.slice(0, -1);
}

function fenceFor(lines: string[]): string {
  let longest = 0;
  for (const line of lines) {
    for (const run of line.match(/`+/g) ?? []) longest = Math.max(longest, run.length);
  }
  return "`".repeat(Math.max(3, longest + 1));
}

export function normalizeOptionHelp(text: string | null | undefined): string {
  if (!text) return "";
  const lines = text.replace(/\r\n?/g, "\n").replace(/\t/g, "    ").split("\n");
  // The author's wrap width, estimated from the longest unindented line.
  const wrapWidth = Math.max(0, ...lines.filter((l) => indentOf(l) < 4).map((l) => l.trimEnd().length));
  let previousSourceLength = 0;
  const out: string[] = [];
  let kind: Kind = "none";
  let paragraphIndent = 0;
  let listContentIndent = 0;
  // Indentation of the source line that started the last output line.
  let lineStartIndent = 0;
  // Set when the previous non-blank line introduced a literal block.
  let literalIntroIndent: number | null = null;

  const pushBlankIfNeeded = () => {
    if (out.length > 0 && out[out.length - 1] !== "") out.push("");
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i].trimEnd();
    const content = raw.trim();
    const indent = indentOf(raw);

    if (content === "") {
      if (out.length > 0 && out[out.length - 1] !== "") out.push("");
      kind = "blank";
      continue;
    }

    // An indented block after "...::" or "Example:" becomes a code block.
    if (literalIntroIndent !== null && indent > literalIntroIndent) {
      const block: string[] = [];
      let j = i;
      for (; j < lines.length; j++) {
        const candidate = lines[j].trimEnd();
        if (candidate.trim() !== "" && indentOf(candidate) <= literalIntroIndent) break;
        block.push(candidate);
      }
      while (block.length > 0 && block[block.length - 1].trim() === "") block.pop();
      const base = Math.min(...block.filter((l) => l.trim() !== "").map(indentOf));
      const body = block.map((l) => l.slice(Math.min(base, indentOf(l))));
      const fence = fenceFor(body);
      pushBlankIfNeeded();
      out.push(fence, ...body, fence, "");
      i = j - 1;
      kind = "code";
      literalIntroIndent = null;
      continue;
    }

    // Author-written Markdown fences pass through untouched.
    if (FENCE.test(content)) {
      const marker = FENCE.exec(content)![1];
      pushBlankIfNeeded();
      out.push(content);
      let j = i + 1;
      for (; j < lines.length; j++) {
        const inner = lines[j].trimEnd();
        out.push(inner.slice(Math.min(indent, indentOf(inner))));
        if (inner.trim().startsWith(marker)) break;
      }
      i = j;
      kind = "code";
      literalIntroIndent = null;
      continue;
    }

    literalIntroIndent = null;

    let line = raw;
    let introducesLiteral = false;
    if (content.endsWith("::")) {
      const stripped = stripLiteralMarker(raw);
      introducesLiteral = true;
      if (stripped === null) {
        literalIntroIndent = indent;
        continue;
      }
      line = stripped;
    }
    const lineContent = line.trim();

    const previous = out.length > 0 ? out[out.length - 1] : "";
    const previousContent = previous.trim();
    const isList =
      LIST_ITEM.test(lineContent) ||
      (PLUS_ITEM.test(lineContent) && (previous === "" || PLUS_ITEM.test(previousContent)));
    const previousWasShort = wrapWidth >= 40 && previousSourceLength < wrapWidth * 0.5;
    previousSourceLength = line.trimEnd().length;

    const breaksHere =
      isList ||
      (kind !== "text" && kind !== "list") ||
      previousWasShort ||
      previousContent.endsWith(":") ||
      /( {2}|\\)$/.test(previous) ||
      STRUCTURAL.test(lineContent) ||
      STRUCTURAL.test(previousContent) ||
      RULE.test(lineContent) ||
      RULE.test(previousContent) ||
      BANNER_END.test(previousContent) ||
      (lineContent.startsWith("(") && (previousContent.endsWith(")") || lineContent.endsWith(")"))) ||
      isLabelLine(lineContent, previousContent);

    let joined = false;
    if (!breaksHere) {
      if (kind === "list" && Math.abs(indent - listContentIndent) <= 1 && indent > 0) joined = true;
      else if (kind === "text" && indent === paragraphIndent) joined = true;
    }

    if (joined) {
      out[out.length - 1] = `${previous.trimEnd()} ${lineContent}`;
    } else {
      // An indented line straight after a blank line would render as an
      // indented code block; only real examples should look like code.
      const startsBlock = out.length === 0 || previous === "";
      out.push(startsBlock && indent >= 4 ? lineContent : line);
      lineStartIndent = indent;
      if (isList) {
        const marker = /^([-*+•]|\d{1,3}[.)])\s+/.exec(lineContent)![0];
        listContentIndent = indent + marker.length;
        kind = "list";
      } else if (kind === "list" && indent > 0) {
        // Indented but not at the item's text column: keep it inside the item.
        kind = "other";
      } else {
        kind = "text";
        paragraphIndent = indent;
      }
    }

    const current = out[out.length - 1].trim();
    if (introducesLiteral || (current.endsWith(":") && EXAMPLE_INTRO.test(current))) {
      literalIntroIndent = lineStartIndent;
    }
  }

  while (out.length > 0 && out[out.length - 1] === "") out.pop();
  return out.join("\n");
}
