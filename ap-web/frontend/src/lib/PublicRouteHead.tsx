import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const PROD_ORIGIN = "https://ap-pie.com";

const PUBLIC_ROUTE_HEAD: Record<string, {
  title: string;
  description: string;
  canonical: string;
}> = {
  "/": {
    title: "Archipelago Multiworld Tools & Guides | Archipelago Pie",
    description: "Build player YAMLs, browse community APWorlds, and learn how to join, host, and play Archipelago multiworld randomizers.",
    canonical: `${PROD_ORIGIN}/`,
  },
  "/apworlds": {
    title: "APWorld Downloads & YAML Builder | Archipelago Pie",
    description: "Browse APWorld downloads by game and version, find setup guides, and build compatible player YAMLs for Archipelago multiworlds.",
    canonical: `${PROD_ORIGIN}/apworlds`,
  },
  "/yaml-builder": {
    title: "Archipelago YAML Builder | Archipelago Pie",
    description: "Build an Archipelago player YAML from guided game options, review the generated file, and download it for your host or multiworld.",
    canonical: `${PROD_ORIGIN}/yaml-builder`,
  },
};

function setMeta(selector: string, attribute: "name" | "property", key: string, content: string) {
  let meta = document.head.querySelector<HTMLMetaElement>(selector);
  if (!meta) {
    meta = document.createElement("meta");
    meta.setAttribute(attribute, key);
    document.head.appendChild(meta);
  }
  meta.content = content;
}

/** Keep search/social head data correct after React Router navigation. */
export default function PublicRouteHead() {
  const { pathname } = useLocation();

  useEffect(() => {
    const route = PUBLIC_ROUTE_HEAD[pathname];
    if (!route) return;

    document.title = route.title;
    setMeta('meta[name="description"]', "name", "description", route.description);
    setMeta('meta[property="og:title"]', "property", "og:title", route.title);
    setMeta('meta[property="og:description"]', "property", "og:description", route.description);
    setMeta('meta[property="og:url"]', "property", "og:url", route.canonical);

    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.rel = "canonical";
      document.head.appendChild(canonical);
    }
    canonical.href = route.canonical;
  }, [pathname]);

  return null;
}
