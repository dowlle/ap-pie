import type { ReactNode } from "react";

/**
 * Lightweight YAML syntax highlighter for YamlViewerModal.
 * Not a full parser; just enough for AP YAMLs (comments, keys, strings,
 * numbers, booleans, null, list bullets, inline comments).
 */

type Tok = { cls: string | null; text: string };

function findInlineCommentStart(s: string): number {
  let inSingle = false;
  let inDouble = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (!inSingle && c === '"') inDouble = !inDouble;
    else if (!inDouble && c === "'") inSingle = !inSingle;
    else if (!inSingle && !inDouble && c === "#") {
      if (i === 0 || /\s/.test(s[i - 1])) return i;
    }
  }
  return -1;
}

function classifyValue(v: string): string {
  if ((v.startsWith('"') && v.endsWith('"') && v.length > 1) ||
      (v.startsWith("'") && v.endsWith("'") && v.length > 1)) {
    return "yh-string";
  }
  if (/^-?\d+(\.\d+)?$/.test(v)) return "yh-number";
  if (/^(true|false|yes|no)$/i.test(v)) return "yh-bool";
  if (/^(null|~)$/i.test(v)) return "yh-null";
  if (/^[|>][+-]?\d*$/.test(v)) return "yh-punct";
  if (v.startsWith("&")) return "yh-anchor";
  if (v.startsWith("*")) return "yh-anchor";
  return "yh-plain";
}

function tokenizeLine(line: string): Tok[] {
  const out: Tok[] = [];

  // Leading indent
  let i = 0;
  while (i < line.length && (line[i] === " " || line[i] === "\t")) i++;
  if (i > 0) out.push({ cls: null, text: line.slice(0, i) });
  let rest = line.slice(i);

  if (rest.length === 0) return out;

  // Whole-line comment
  if (rest.startsWith("#")) {
    out.push({ cls: "yh-comment", text: rest });
    return out;
  }

  // List bullet
  if (rest.startsWith("- ")) {
    out.push({ cls: "yh-punct", text: "- " });
    rest = rest.slice(2);
  } else if (rest === "-") {
    out.push({ cls: "yh-punct", text: "-" });
    return out;
  }

  // Key: (followed by whitespace or end-of-line)
  const keyMatch = rest.match(/^([^:#\s][^:]*?):(?=\s|$)/);
  if (keyMatch) {
    out.push({ cls: "yh-key", text: keyMatch[1] });
    out.push({ cls: "yh-punct", text: ":" });
    rest = rest.slice(keyMatch[0].length);
    const wsLen = rest.match(/^\s+/)?.[0].length ?? 0;
    if (wsLen > 0) {
      out.push({ cls: null, text: rest.slice(0, wsLen) });
      rest = rest.slice(wsLen);
    }
  }

  if (rest.length === 0) return out;

  // Split off inline comment (# preceded by whitespace, outside quotes)
  const inlineIdx = findInlineCommentStart(rest);
  let valuePart = inlineIdx === -1 ? rest : rest.slice(0, inlineIdx);
  const commentPart = inlineIdx === -1 ? "" : rest.slice(inlineIdx);

  // Preserve trailing whitespace inside the value as a non-coloured token
  const trailingWsMatch = valuePart.match(/(\s+)$/);
  const trailingWs = trailingWsMatch ? trailingWsMatch[0] : "";
  if (trailingWs) valuePart = valuePart.slice(0, valuePart.length - trailingWs.length);

  if (valuePart.length > 0) out.push({ cls: classifyValue(valuePart), text: valuePart });
  if (trailingWs) out.push({ cls: null, text: trailingWs });
  if (commentPart) out.push({ cls: "yh-comment", text: commentPart });

  return out;
}

export function highlightYaml(content: string): ReactNode {
  const lines = content.split("\n");
  return lines.map((line, lineIdx) => (
    <span key={lineIdx}>
      {tokenizeLine(line).map((t, j) =>
        t.cls === null
          ? <span key={j}>{t.text}</span>
          : <span key={j} className={t.cls}>{t.text}</span>
      )}
      {lineIdx < lines.length - 1 ? "\n" : ""}
    </span>
  ));
}
