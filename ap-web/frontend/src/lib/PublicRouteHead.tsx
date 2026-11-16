import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { applyPublicHead, setMeta } from "./publicHead";

const PROD_ORIGIN = "https://ap-pie.com";

const PUBLIC_ROUTE_HEAD: Record<string, {
  title: string;
  description: string;
  canonical: string;
  robots?: string;
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
  "/style-guide": {
    title: "AP-Pie Visual Style Guide",
    description: "A private beta review surface for AP-Pie's proposed shared visual system.",
    canonical: `${PROD_ORIGIN}/style-guide`,
    robots: "noindex, nofollow",
  },

};

/** Keep search/social head data correct after React Router navigation. */
export default function PublicRouteHead() {
  const { pathname } = useLocation();

  useEffect(() => {
    const isPrivate = pathname === "/my" || pathname.startsWith("/my/")
      || pathname === "/account-recovery";
    if (isPrivate) {
      setMeta('meta[name="robots"]', "name", "robots", "noindex, nofollow");
      document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.remove();
      document.head.querySelector<HTMLMetaElement>('meta[property="og:url"]')?.remove();
      return () => {
        document.head.querySelector<HTMLMetaElement>('meta[name="robots"]')?.remove();
      };
    }

    const route = PUBLIC_ROUTE_HEAD[pathname];
    if (!route) return;

    applyPublicHead(route);
    const existingRobots = document.head.querySelector<HTMLMetaElement>('meta[name="robots"]');
    if (route.robots) {
      setMeta('meta[name="robots"]', "name", "robots", route.robots);
    } else {
      existingRobots?.remove();
    }
  }, [pathname]);

  return null;
}
