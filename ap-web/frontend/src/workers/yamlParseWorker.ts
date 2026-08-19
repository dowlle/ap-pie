import { parseDocument } from "yaml";
import type { ParsedTemplate } from "../api";
import { importYaml, type ImportedYaml } from "../lib/yamlImport";

type ParseRequest = {
  text: string;
  schema: ParsedTemplate;
};

export type ParseResponse =
  | { ok: true; parsed: ImportedYaml }
  | { ok: false; message: string };

self.onmessage = (event: MessageEvent<ParseRequest>) => {
  const { text, schema } = event.data;
  const document = parseDocument(text);
  if (document.errors.length > 0) {
    self.postMessage({
      ok: false,
      message: document.errors[0]?.message.split(" at line")[0]
        || "Fix the YAML syntax to resume syncing.",
    } satisfies ParseResponse);
    return;
  }

  const parsed = importYaml(text, schema);
  self.postMessage(parsed
    ? { ok: true, parsed }
    : {
        ok: false,
        message: "The document needs a name, game and option mapping before it can sync.",
      } satisfies ParseResponse);
};
