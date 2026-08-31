import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getFeatures, type Features } from "../api";

/**
 * Read-only context exposing the server's feature flag state.
 * Frontend uses useFeature(name) to gate UI surfaces (hide buttons, nav
 * links, etc.). The flags themselves are env-driven in config.py and exposed
 * via GET /api/features.
 *
 * If the fetch fails (network error / endpoint missing on a legacy deploy),
 * defaults conservatively for access-changing features when the endpoint is
 * unavailable. Generation retains its historical compatibility default.
 */

const SAFE_DEFAULTS: Features = {
  generation: true,
  open_room_creation: false,
};

const FeaturesContext = createContext<Features>(SAFE_DEFAULTS);

export function FeaturesProvider({ children }: { children: ReactNode }) {
  const [features, setFeatures] = useState<Features>(SAFE_DEFAULTS);
  useEffect(() => {
    getFeatures()
      .then(setFeatures)
      .catch(() => {
        // Endpoint missing or network error - leave conservative defaults.
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
