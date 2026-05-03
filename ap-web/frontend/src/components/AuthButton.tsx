import { useAuth } from "../context/AuthContext";

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
      <span className="auth-username">{user?.discord_username}</span>
      <button onClick={logout} className="btn btn-sm">
        Logout
      </button>
    </div>
  );
}
