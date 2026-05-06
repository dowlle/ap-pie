import { useDeploymentLabel } from "../context/DeploymentContext";

/**
 * OPS-07: persistent banner for non-prod environments.
 *
 * Renders nothing on prod (empty label) and a high-contrast strip across
 * the top of the viewport for any non-empty label. Currently the only
 * label that ships is "beta" (the deploy at beta.ap-pie.com). Other
 * labels would render the same chrome with the literal label text in
 * the strip — so e.g. AP_DEPLOYMENT_LABEL=staging would render "STAGING
 * — data resets without warning, not for real syncs."
 *
 * Pure visual: no interactive state, no dismiss, no localStorage. The
 * banner is the entire point of having a labelled environment; letting
 * a tester dismiss it would silently undo the visual cue.
 */
export default function DeploymentBanner() {
  const label = useDeploymentLabel();
  if (!label) return null;

  const upper = label.toUpperCase();

  return (
    <div className="deployment-banner" role="status" aria-live="polite">
      <strong>{upper}</strong>
      <span className="deployment-banner-copy">
        — data resets without warning, not for real syncs.
      </span>
    </div>
  );
}
