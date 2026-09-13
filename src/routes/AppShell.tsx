import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Plane } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useAuthUser } from "./ProtectedRoute";
import { useDocumentTitle } from "@/hooks/use-document-title";

export default function AppShell() {
  const user = useAuthUser();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useDocumentTitle("Dashboard — Flight Price Notifier");

  async function signOut() {
    await queryClient.cancelQueries();
    queryClient.clear();
    await supabase.auth.signOut();
    navigate("/auth", { replace: true });
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border/60">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4">
          <span className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid size-7 place-items-center rounded-lg bg-primary/15 text-primary">
              <Plane className="size-4" />
            </span>
            Flight Price Notifier
          </span>
          <button
            type="button"
            onClick={signOut}
            className="rounded-full border border-border px-4 py-2 text-sm transition hover:border-primary/60 hover:text-primary"
          >
            Sign out / 登出
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 py-20">
        <h1 className="text-3xl font-semibold tracking-tight">Hi {user.email}</h1>
        <div className="mt-8 rounded-2xl border border-border bg-card p-8">
          <p className="text-base">
            你的航線追蹤儀表板即將上線 — 下一個里程碑會加上訂閱航線的功能。
          </p>
          <p className="mt-3 text-sm text-muted-foreground">
            Your dashboard is coming soon. Route-subscription will be added in the next milestone.
          </p>
        </div>
      </main>
    </div>
  );
}
