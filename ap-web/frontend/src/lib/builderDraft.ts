const HANDOFF = "ap-pie:builder-login-handoff";

/** Explicit, tab-local handoff only. Never migrate another account's draft. */
export function signInWithBuilderDraft(draftKey?: string) {
  const returnPath = location.pathname + location.search;
  if (draftKey?.startsWith("ap-pie:yaml-builder:anonymous:")) {
    sessionStorage.setItem(HANDOFF, JSON.stringify({ draftKey, returnPath }));
  }
  location.assign(`/api/auth/login?next=${encodeURIComponent(returnPath)}`);
}

export function pendingBuilderDraft(targetKey: string): string | null {
  try {
    const handoff = JSON.parse(sessionStorage.getItem(HANDOFF) || "null");
    if (!handoff || handoff.returnPath !== location.pathname + location.search ||
        !handoff.draftKey?.startsWith("ap-pie:yaml-builder:anonymous:") ||
        targetKey.includes(":anonymous:") ||
        handoff.draftKey.split(":").slice(3).join(":") !== targetKey.split(":").slice(3).join(":")) return null;
    return sessionStorage.getItem(handoff.draftKey);
  } catch { return null; }
}

export function finishBuilderDraftHandoff(targetKey: string, useIncoming: boolean) {
  const incoming = pendingBuilderDraft(targetKey);
  if (incoming && useIncoming) sessionStorage.setItem(targetKey, incoming);
  // Keep original bytes when the user chooses their existing draft.
  if (incoming && useIncoming) {
    const handoff = JSON.parse(sessionStorage.getItem(HANDOFF)!);
    sessionStorage.removeItem(handoff.draftKey);
  }
  sessionStorage.removeItem(HANDOFF);
}
