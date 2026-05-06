import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getDeployment, type Deployment } from "../api";

/**
 * OPS-07: deployment-environment context.
 *
 * Empty `label` means prod / unlabelled — no banner renders. A non-empty
 * label (e.g. "beta") triggers <DeploymentBanner> above the NavBar and
 * PublicLayout header so testers never confuse the two environments.
 *
 * If the fetch fails (network error / endpoint missing on a legacy deploy
 * that doesn't have it yet), defaults to empty string so prod-shaped
 * deployments never accidentally show a banner.
 */

const EMPTY: Deployment = { label: "" };

const DeploymentContext = createContext<Deployment>(EMPTY);

export function DeploymentProvider({ children }: { children: ReactNode }) {
  const [deployment, setDeployment] = useState<Deployment>(EMPTY);
  useEffect(() => {
    getDeployment()
      .then(setDeployment)
      .catch(() => {
        // Endpoint missing or network error — leave empty (no banner).
      });
  }, []);
  return <DeploymentContext.Provider value={deployment}>{children}</DeploymentContext.Provider>;
}

export function useDeployment(): Deployment {
  return useContext(DeploymentContext);
}

export function useDeploymentLabel(): string {
  return useContext(DeploymentContext).label;
}
