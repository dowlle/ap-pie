import { useAuth } from "../context/AuthContext";
import { Link } from "react-router-dom";

export default function AuthButton() {
  const { user, isAuthenticated, authEnabled, loading, login, logout } = useAuth();

  if (loading || !authEnabled) return null;

  if (!isAuthenticated) {
    return (
      <button onClick={() => login()} className="btn btn-sm btn-primary">
        Sign in with Discord
      </button>
    );
  }

  return (
    <div className="auth-user">
      <Link className="auth-username" to="/my/account">{user?.discord_username}</Link>
      <button onClick={logout} className="btn btn-sm">
        Logout
      </button>
    </div>
  );
}
