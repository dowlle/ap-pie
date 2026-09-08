export default function FavoriteGameButton({ name, saved, disabled, onClick, iconOnly = false }: {
  name: string; saved: boolean; disabled: boolean; onClick: () => void; iconOnly?: boolean;
}) {
  const tooltip = saved ? "Remove from favorite games" : "Save to favorite games";
  return <button type="button" className={`btn btn-sm favorite-game-button${iconOnly ? " apworld-action apworld-favorite-btn" : ""}`} aria-pressed={saved}
    aria-label={`${saved ? "Remove" : "Add"} ${name} ${saved ? "from" : "to"} favorite games`}
    data-tooltip={iconOnly ? tooltip : undefined}
    title={iconOnly ? undefined : tooltip}
    disabled={disabled} onClick={onClick}>
    <svg viewBox="0 0 24 24" width="16" height="16" fill={saved ? "currentColor" : "none"}
      stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
      <path d="m12 3 2.8 5.7 6.3.9-4.55 4.45 1.07 6.28L12 17.36l-5.62 2.97 1.07-6.28L2.9 9.6l6.3-.9Z" />
    </svg>
    {!iconOnly && (saved ? "Saved favorite" : "Save favorite")}
  </button>;
}
