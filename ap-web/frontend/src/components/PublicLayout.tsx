import { Outlet } from "react-router-dom";
import DeploymentBanner from "./DeploymentBanner";
import SiteHeader from "./SiteHeader";

/** Public content shell. It shares the canonical role-aware site header with
 * application pages while retaining the wider, room-oriented main canvas. */
export default function PublicLayout() {
  return (
    <div className="public-shell">
      <DeploymentBanner />
      <SiteHeader />
      <main className="public-shell-main">
        <Outlet />
      </main>
    </div>
  );
}
