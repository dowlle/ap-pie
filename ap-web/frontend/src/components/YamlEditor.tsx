import { useEffect, useState } from "react";
import {
  getTemplateList,
  getTemplate,
  createYamlFromEditor,
  type TemplateListItem,
  type ParsedTemplate,
  type TemplateOption,
} from "../api";

interface Props {
  roomId: string;
  onComplete: () => void;
  onCancel: () => void;
}

function OptionInput({ option, value, onChange }: {
  option: TemplateOption;
  value: any;
  onChange: (val: any) => void;
}) {
  switch (option.type) {
    case "toggle":
      return (
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
          />
          <span>{value ? "true" : "false"}</span>
        </label>
      );

    case "choice":
      return (
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {option.choices?.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      );

    case "range": {
      const named = option.named_values;
      const matchingAlias = named
        ? Object.entries(named).find(([, v]) => v === value)?.[0]
        : undefined;

      return (
        <div className="range-input">
          <input
            type="number"
            min={option.min}
            max={option.max}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
          />
          <input
            type="range"
            min={option.min}
            max={option.max}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="range-slider"
          />
          {named && Object.keys(named).length > 0 && (
            <select
              value={matchingAlias ?? ""}
              onChange={(e) => {
                if (e.target.value && named[e.target.value] !== undefined) {
                  onChange(named[e.target.value]);
                }
              }}
            >
              <option value="">Custom</option>
              {Object.entries(named).map(([name, num]) => (
                <option key={name} value={name}>{name} ({num})</option>
              ))}
            </select>
          )}
        </div>
      );
    }

    case "list":
      return (
        <textarea
          value={Array.isArray(value) ? value.join(", ") : value}
          onChange={(e) => {
            const text = e.target.value;
            onChange(text ? text.split(",").map((s: string) => s.trim()).filter(Boolean) : []);
          }}
          placeholder="Comma-separated values (leave empty for default)"
          rows={2}
        />
      );

    case "dict":
      return (
        <textarea
          value={typeof value === "string" ? value : Object.entries(value || {}).map(([k, v]) => `${k}: ${v}`).join("\n")}
          onChange={(e) => onChange(e.target.value)}
          placeholder="key: value (one per line)"
          rows={3}
        />
      );

    default:
      return <input type="text" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
  }
}

function buildYaml(game: string, playerName: string, options: Record<string, any>, template: ParsedTemplate): string {
  const lines: string[] = [];
  lines.push(`name: ${playerName}`);
  lines.push(`description: Created via YAML Editor`);
  lines.push(`game: ${game}`);

  if (template.ap_version) {
    lines.push(`requires:`);
    lines.push(`  version: ${template.ap_version}`);
  }

  lines.push("");
  lines.push(`${game}:`);

  let currentCategory = "";
  for (const opt of template.options) {
    if (opt.category !== currentCategory) {
      currentCategory = opt.category;
      lines.push("");
      const border = "#".repeat(currentCategory.length + 4);
      lines.push(`  ${border}`);
      lines.push(`  # ${currentCategory} #`);
      lines.push(`  ${border}`);
    }

    const val = options[opt.name] ?? opt.default;

    // Format value based on type
    if (opt.type === "toggle") {
      lines.push(`  ${opt.name}: ${val ? "true" : "false"}`);
    } else if (opt.type === "range") {
      lines.push(`  ${opt.name}: ${val}`);
    } else if (opt.type === "list") {
      if (Array.isArray(val) && val.length > 0) {
        lines.push(`  ${opt.name}:`);
        for (const item of val) {
          lines.push(`    - ${item}`);
        }
      } else {
        lines.push(`  ${opt.name}: []`);
      }
    } else if (opt.type === "dict") {
      if (typeof val === "string" && val.trim()) {
        lines.push(`  ${opt.name}:`);
        for (const line of val.split("\n")) {
          if (line.trim()) lines.push(`    ${line.trim()}`);
        }
      } else if (typeof val === "object" && val && Object.keys(val).length > 0) {
        lines.push(`  ${opt.name}:`);
        for (const [k, v] of Object.entries(val)) {
          lines.push(`    ${k}: ${v}`);
        }
      } else {
        lines.push(`  ${opt.name}: {}`);
      }
    } else {
      // Choice or other string values
      const needsQuote = val === "true" || val === "false" || val === "null" || val === "";
      lines.push(`  ${opt.name}: ${needsQuote ? `'${val}'` : val}`);
    }
  }

  return lines.join("\n") + "\n";
}

export default function YamlEditor({ roomId, onComplete, onCancel }: Props) {
  const [templates, setTemplates] = useState<TemplateListItem[]>([]);
  const [selectedGame, setSelectedGame] = useState("");
  const [template, setTemplate] = useState<ParsedTemplate | null>(null);
  const [playerName, setPlayerName] = useState("Player1");
  const [values, setValues] = useState<Record<string, any>>({});
  const [collapsedCats, setCollapsedCats] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getTemplateList().then(setTemplates).catch(() => setError("Failed to load templates"));
  }, []);

  const handleGameSelect = async (game: string) => {
    setSelectedGame(game);
    setTemplate(null);
    setValues({});
    setError("");
    if (!game) return;

    setLoading(true);
    try {
      const t = await getTemplate(game);
      setTemplate(t);
      // Initialize values with defaults
      const defaults: Record<string, any> = {};
      for (const opt of t.options) {
        defaults[opt.name] = opt.default;
      }
      setValues(defaults);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load template");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!template) return;
    setSubmitting(true);
    setError("");
    try {
      const yamlContent = buildYaml(selectedGame, playerName, values, template);
      await createYamlFromEditor(roomId, {
        player_name: playerName,
        game: selectedGame,
        yaml_content: yamlContent,
      });
      onComplete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create YAML");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleCategory = (cat: string) => {
    setCollapsedCats((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  return (
    <div className="yaml-editor">
      <div className="yaml-editor-header">
        <h3>Create YAML</h3>
        <button className="btn btn-sm" onClick={onCancel}>Cancel</button>
      </div>

      <div className="yaml-editor-top">
        <div className="yaml-editor-field">
          <label>Game</label>
          <select value={selectedGame} onChange={(e) => handleGameSelect(e.target.value)}>
            <option value="">Select a game...</option>
            {templates.map((t) => (
              <option key={t.game} value={t.game}>{t.game}</option>
            ))}
          </select>
        </div>
        <div className="yaml-editor-field">
          <label>Player Name</label>
          <input
            type="text"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            maxLength={16}
            placeholder="Your name (max 16 chars)"
          />
        </div>
      </div>

      {error && <p className="upload-error">{error}</p>}
      {loading && <p className="loading">Loading template...</p>}

      {template && (
        <>
          <div className="yaml-editor-info">
            {template.world_version && <span className="badge">v{template.world_version}</span>}
            <span className="muted">{template.options.length} options</span>
          </div>

          <div className="yaml-editor-options">
            {template.categories.map((cat) => {
              const catOptions = template.options.filter((o) => o.category === cat);
              if (catOptions.length === 0) return null;
              const collapsed = collapsedCats.has(cat);

              return (
                <div key={cat} className="yaml-editor-category">
                  <button
                    className="yaml-editor-cat-header"
                    onClick={() => toggleCategory(cat)}
                  >
                    <span>{collapsed ? "+" : "-"}</span>
                    <span>{cat}</span>
                    <span className="muted">({catOptions.length})</span>
                  </button>
                  {!collapsed && (
                    <div className="yaml-editor-cat-body">
                      {catOptions.map((opt) => (
                        <div key={opt.name} className="yaml-editor-option">
                          <div className="yaml-editor-option-header">
                            <code className="option-name">{opt.name}</code>
                            <span className="badge badge-sm">{opt.type}</span>
                          </div>
                          {opt.description && (
                            <p className="option-desc">{opt.description}</p>
                          )}
                          <div className="option-input">
                            <OptionInput
                              option={opt}
                              value={values[opt.name]}
                              onChange={(val) => setValues((prev) => ({ ...prev, [opt.name]: val }))}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="yaml-editor-actions">
            <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting || !playerName.trim()}>
              {submitting ? "Creating..." : "Create YAML"}
            </button>
            <button className="btn" onClick={onCancel}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}
