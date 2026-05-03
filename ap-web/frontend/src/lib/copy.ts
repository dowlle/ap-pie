/**
 * Copy text to clipboard with a fallback for insecure contexts.
 *
 * `navigator.clipboard.writeText` is only available in secure contexts
 * (HTTPS or localhost). On plain-HTTP LAN deployments like http://192.168.x.x
 * it's undefined, so we fall back to the classic `document.execCommand("copy")`
 * trick with an off-screen textarea. That pathway still works on every
 * browser we care about, even though the spec marks it deprecated.
 */
export async function copyText(value: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // fall through to the textarea fallback
    }
  }

  try {
    const ta = document.createElement("textarea");
    ta.value = value;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "-1000px";
    ta.style.left = "-1000px";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}
