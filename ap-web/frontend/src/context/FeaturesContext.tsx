import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getFeatures, type Features } from "../api";

/**
 * Read-only context exposing the server's feature flag state.
 * Frontend uses useFeature(name) to gate UI surfaces (hide buttons, nav
 * links, etc.). The flags themselves are env-driven in config.py and exposed
 * via GET /api/features.
 *
 * If the fetch fails (network error / endpoint missing on a legacy deploy),
 * defaults to ALL ON - backward compat for older Atlas-style deployments
 * that haven't picked up this commit yet.
 */

const ALL_ON: Features = {
  generation: true,
};

const FeaturesContext = createContext<Features>(ALL_ON);

export function FeaturesProvider({ children }: { children: ReactNode }) {
  const [features, setFeatures] = useState<Features>(ALL_ON);
  useEffect(() => {
    getFeatures()
      .then(setFeatures)
      .catch(() => {
        // Endpoint missing or network error - leave defaults (all on).
      });
  }, []);
  return <FeaturesContext.Provider value={features}>{children}</FeaturesContext.Provider>;
}

export function useFeature(name: keyof Features): boolean {
  return useContext(FeaturesContext)[name];
}

export function useFeatures(): Features {
  return useContext(FeaturesContext);
}
