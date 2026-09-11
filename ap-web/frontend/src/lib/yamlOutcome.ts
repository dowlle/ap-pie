import type { SubmitResult } from "../api";

export function yamlOutcome(result: SubmitResult): string {
  const identity = `${result.player_name} (${result.game})`;
  if (result.validation_status === "failed") return `${identity} was stored but needs correction: ${result.validation_error || "validation failed"}. Open the room to edit it before generation.`;
  const warnings = result.option_warnings ?? [];
  if (warnings.length) return `${identity} was stored with ${warnings.length} option warning${warnings.length === 1 ? "" : "s"}: ${warnings.map(w => w.detail).join(" ")}. Open the room to review and edit.`;
  return `${identity} - ${result.validation_status}. Open the room to check its status or edit your submission. Final compatibility is confirmed during generation.`;
}
