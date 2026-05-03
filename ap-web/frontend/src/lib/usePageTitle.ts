import { useEffect } from "react";

const DEFAULT_TITLE = "Archipelago Pie - multiworld lobby & tracker";

/**
 * Set document.title for the duration of the current route.
 *
 * Pass null/empty to reset to the default. The hook restores the previous
 * title on unmount so navigating between pages doesn't strand a stale title
 * on a different route.
 */
export function usePageTitle(title: string | null | undefined) {
  useEffect(() => {
    if (!title) {
      document.title = DEFAULT_TITLE;
      return;
    }
    document.title = `${title} · Archipelago Pie`;
    return () => {
      document.title = DEFAULT_TITLE;
    };
  }, [title]);
}
