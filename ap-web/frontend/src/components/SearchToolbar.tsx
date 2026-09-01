interface SearchToolbarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  label: string;
  resultCount?: number;
  totalCount?: number;
}

export default function SearchToolbar({
  value,
  onChange,
  placeholder,
  label,
  resultCount,
  totalCount,
}: SearchToolbarProps) {
  return (
    <div className="search-toolbar" role="search">
      <label className="shared-field search-toolbar-field">
        <span className="sr-only">{label}</span>
        <input
          type="search"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
        />
      </label>
      {value.trim() && resultCount !== undefined && totalCount !== undefined && (
        <span className="muted search-toolbar-count" aria-live="polite">
          {resultCount} of {totalCount}
        </span>
      )}
    </div>
  );
}
