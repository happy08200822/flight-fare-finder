import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import type { User } from "@supabase/supabase-js";
import { supabase } from "@/integrations/supabase/client";

const AuthUserContext = createContext<User | null>(null);

export function useAuthUser(): User {
  const user = useContext(AuthUserContext);
  if (!user) throw new Error("useAuthUser must be used within a ProtectedRoute");
  return user;
}

type AuthState = { status: "loading" } | { status: "anon" } | { status: "authed"; user: User };

export default function ProtectedRoute() {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    supabase.auth.getUser().then(({ data, error }) => {
      if (!active) return;
      if (error || !data.user) setState({ status: "anon" });
      else setState({ status: "authed", user: data.user });
    });
    return () => {
      active = false;
    };
  }, []);

  if (state.status === "loading") return null;
  if (state.status === "anon") return <Navigate to="/auth" replace />;

  return (
    <AuthUserContext.Provider value={state.user}>
      <Outlet />
    </AuthUserContext.Provider>
  );
}
