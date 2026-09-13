import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { Plane } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function AuthPage({
  defaultMode = "signin",
}: {
  defaultMode?: "signin" | "signup";
}) {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"signin" | "signup">(defaultMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useDocumentTitle(
    mode === "signin" ? "Sign in — Flight Price Notifier" : "Sign up — Flight Price Notifier",
  );

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) navigate("/app", { replace: true });
    });
  }, [navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { data, error } =
      mode === "signin"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({
            email,
            password,
            options: { emailRedirectTo: window.location.origin },
          });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    if (!data.session) {
      setError("請先到信箱確認你的 email，再回來登入。");
      return;
    }
    navigate("/app", { replace: true });
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b border-border/60">
        <div className="mx-auto flex max-w-6xl items-center px-5 py-4">
          <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid size-7 place-items-center rounded-lg bg-primary/15 text-primary">
              <Plane className="size-4" />
            </span>
            Flight Price Notifier
          </Link>
        </div>
      </header>

      <main className="relative flex flex-1 items-center justify-center px-5 py-16">
        <div className="pointer-events-none absolute top-0 left-1/2 size-[32rem] -translate-x-1/2 rounded-full bg-primary/15 blur-[120px]" />
        <div className="relative w-full max-w-md rounded-2xl border border-border bg-card p-8">
          <h1 className="text-2xl font-semibold">
            {mode === "signin" ? "登入 / Sign in" : "註冊 / Sign up"}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            使用 email 與密碼{mode === "signin" ? "登入" : "建立帳號"}。
          </p>

          <form onSubmit={onSubmit} className="mt-7 space-y-4">
            <div>
              <label htmlFor="email" className="text-sm text-muted-foreground">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-primary"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label htmlFor="password" className="text-sm text-muted-foreground">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-primary"
                placeholder="••••••••"
              />
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-60"
            >
              {loading ? "請稍候…" : mode === "signin" ? "Sign in / 登入" : "Sign up / 註冊"}
            </button>
          </form>

          <button
            type="button"
            onClick={() => {
              setMode(mode === "signin" ? "signup" : "signin");
              setError(null);
            }}
            className="mt-6 w-full text-sm text-muted-foreground transition hover:text-foreground"
          >
            {mode === "signin" ? "還沒有帳號？註冊 Sign up" : "已經有帳號？登入 Sign in"}
          </button>
        </div>
      </main>
    </div>
  );
}
