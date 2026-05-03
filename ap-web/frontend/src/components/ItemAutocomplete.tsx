import { useEffect, useMemo, useRef, useState } from "react";

interface Catalog {
  game: string;
  categories: Record<string, string[]>;
}

interface Props {
  game: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function ItemAutocomplete({ game, value, onChange, placeholder }: Props) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Load catalog for the game
  useEffect(() => {
    const slug = game.toLowerCase().replace(/\s+/g, "_");
    fetch(`/catalog/games/${slug}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, [game]);

  // All items flattened with category info
  const allItems = useMemo(() => {
    if (!catalog) return [];
    const items: { name: string; category: string }[] = [];
    for (const [cat, names] of Object.entries(catalog.categories)) {
      for (const name of names) {
        items.push({ name, category: cat });
      }
    }
    return items;
  }, [catalog]);

  // Filtered by search
  const filtered = useMemo(() => {
    if (!value.trim()) return allItems.slice(0, 50);
    const lower = value.toLowerCase();
    return allItems.filter((i) => i.name.toLowerCase().includes(lower)).slice(0, 50);
  }, [allItems, value]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter" && highlighted >= 0 && highlighted < filtered.length) {
      e.preventDefault();
      onChange(filtered[highlighted].name);
      setOpen(false);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  // If no catalog, just render a plain input
  if (!catalog) {
    return (
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "Item name..."}
      />
    );
  }

  return (
    <div className="autocomplete-wrapper" ref={wrapperRef}>
      <input
        type="text"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
          setHighlighted(-1);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder ?? "Search items..."}
        autoComplete="off"
      />
      {open && filtered.length > 0 && (
        <div className="autocomplete-dropdown">
          {filtered.map((item, i) => (
            <div
              key={`${item.category}-${item.name}`}
              className={`autocomplete-item ${i === highlighted ? "highlighted" : ""}`}
              onMouseDown={() => {
                onChange(item.name);
                setOpen(false);
              }}
              onMouseEnter={() => setHighlighted(i)}
            >
              <span className="autocomplete-item-name">{item.name}</span>
              <span className="autocomplete-item-category">{item.category}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
