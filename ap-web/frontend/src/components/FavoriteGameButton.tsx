export default function FavoriteGameButton({ name, saved, disabled, onClick }: {
  name: string; saved: boolean; disabled: boolean; onClick: () => void;
}) {
  return <button type="button" className="btn btn-sm" aria-pressed={saved}
    aria-label={`${saved ? "Remove" : "Add"} ${name} ${saved ? "from" : "to"} favorite games`}
    disabled={disabled} onClick={onClick}>
    <span aria-hidden="true">{saved ? "★" : "☆"}</span> {saved ? "Saved favorite" : "Save favorite"}
  </button>;
}
