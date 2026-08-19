import { Link, useLocation } from "react-router-dom";
import { usePageTitle } from "../lib/usePageTitle";

export default function NotFound() {
  const location = useLocation();
  usePageTitle("Page not found");

  return (
    <section className="not-found" aria-labelledby="not-found-title">
      <p className="not-found-code">404</p>
      <h1 id="not-found-title">This page got sent to another world</h1>
      <p>
        There is nothing at <code>{location.pathname}</code>. The link may be old, or the address may have a typo.
      </p>
      <div className="not-found-actions">
        <Link className="btn btn-primary" to="/">Go home</Link>
        <Link className="btn" to="/yaml-builder">Build a YAML</Link>
        <a className="btn" href="/guides">Read the guides</a>
        <Link className="btn" to="/apworlds">Browse APWorlds</Link>
      </div>
    </section>
  );
}
