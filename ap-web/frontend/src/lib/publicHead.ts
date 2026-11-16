const PROD_ORIGIN = "https://ap-pie.com";
export function setMeta(selector: string, attribute: "name" | "property", key: string, content: string) {
  let meta = document.head.querySelector<HTMLMetaElement>(selector);
  if (!meta) {
    meta = document.createElement("meta");
    meta.setAttribute(attribute, key);
    document.head.appendChild(meta);
  }
  meta.content = content;
}

export function applyPublicHead(route: { title: string; description: string; canonical: string }) {
  document.title = route.title;
  for (const [key, content] of Object.entries({
    description: route.description, "twitter:title": route.title,
    "twitter:description": route.description, "twitter:card": "summary_large_image",
    "twitter:image": `${PROD_ORIGIN}/img/guides/og-tools.png`,
  })) setMeta(`meta[name="${key}"]`, "name", key, content);
  for (const [key, content] of Object.entries({
    "og:title": route.title, "og:description": route.description, "og:url": route.canonical,
    "og:image": `${PROD_ORIGIN}/img/guides/og-tools.png`,
  })) setMeta(`meta[property="${key}"]`, "property", key, content);
  let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!canonical) {
    canonical = document.createElement("link");
    canonical.rel = "canonical";
    document.head.appendChild(canonical);
  }
  canonical.href = route.canonical;
  document.head.querySelector('meta[name="robots"]')?.remove();
}
