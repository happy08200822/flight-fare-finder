import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Plane, BellRing } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useAuthUser } from "./ProtectedRoute";
import { useDocumentTitle } from "@/hooks/use-document-title";

const API_BASE = import.meta.env["VITE_FLIGHT_API_URL"];

const PLANS = [
  { plan_name: "tokyo", label: "台北 ✈ 東京", hint: "近期最低約 NT$9,325" },
  { plan_name: "seoul", label: "台北 ✈ 首爾", hint: "近期最低約 NT$5,989" },
] as const;

type Subscription = {
  route: string;
  plan_name: string;
  target_price: number;
  currency: string;
};

export default function AppShell() {
  const user = useAuthUser();
  const email = user.email ?? "";
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useDocumentTitle("Dashboard — Flight Price Notifier");

  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loadingSubs, setLoadingSubs] = useState(true);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!email) return;
    let active = true;
    fetch(`${API_BASE}/subscriptions?email=${encodeURIComponent(email)}`)
      .then((r) => r.json())
      .then((data) => {
        if (active) setSubs(data.items ?? []);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoadingSubs(false);
      });
    return () => {
      active = false;
    };
  }, [email]);

  async function subscribe(planName: string) {
    const raw = drafts[planName];
    const targetPrice = Number(raw);
    if (!raw || !Number.isFinite(targetPrice) || targetPrice <= 0) {
      setErrors((e) => ({ ...e, [planName]: "請輸入有效的目標價" }));
      return;
    }
    setErrors((e) => ({ ...e, [planName]: "" }));
    setSaving(planName);
    try {
      const res = await fetch(`${API_BASE}/subscribe`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, plan_name: planName, target_price: targetPrice }),
      });
      if (!res.ok) throw new Error("subscribe failed");
      const data = await fetch(
        `${API_BASE}/subscriptions?email=${encodeURIComponent(email)}`,
      ).then((r) => r.json());
      setSubs(data.items ?? []);
      setDrafts((d) => ({ ...d, [planName]: "" }));
    } catch {
      setErrors((e) => ({ ...e, [planName]: "訂閱失敗，請稍後再試" }));
    } finally {
      setSaving(null);
    }
  }

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

      <main className="mx-auto max-w-5xl px-5 py-16">
        <h1 className="text-3xl font-semibold tracking-tight">Hi {email}</h1>
        <p className="mt-2 text-muted-foreground">
          選一條航線、設定目標價，機票降到目標價我們就寄信通知你。
        </p>

        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          {PLANS.map((plan) => {
            const sub = subs.find((s) => s.plan_name === plan.plan_name);
            const isSaving = saving === plan.plan_name;
            return (
              <div
                key={plan.plan_name}
                className="rounded-2xl border border-border bg-card p-6"
              >
                <div className="flex items-center justify-between gap-2">
                  <h2 className="flex items-center gap-2 text-lg font-semibold">
                    <Plane className="size-4 text-primary" />
                    {plan.label}
                  </h2>
                  {sub ? (
                    <span className="flex items-center gap-1 rounded-full bg-primary/15 px-3 py-1 text-xs font-medium text-primary">
                      <BellRing className="size-3" />
                      已訂閱
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{plan.hint}</p>

                {sub ? (
                  <p className="mt-4 text-sm">
                    目前目標價：
                    <span className="font-semibold">
                      {" "}
                      NT$ {sub.target_price.toLocaleString()}
                    </span>
                  </p>
                ) : null}

                <div className="mt-4 flex gap-2">
                  <input
                    type="number"
                    min={1}
                    placeholder={sub ? String(sub.target_price) : "目標價 (TWD)"}
                    value={drafts[plan.plan_name] ?? ""}
                    onChange={(e) =>
                      setDrafts((d) => ({ ...d, [plan.plan_name]: e.target.value }))
                    }
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                  />
                  <button
                    type="button"
                    onClick={() => subscribe(plan.plan_name)}
                    disabled={isSaving}
                    className="shrink-0 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-60"
                  >
                    {isSaving ? "儲存中…" : sub ? "更新目標價" : "開始追蹤"}
                  </button>
                </div>
                {errors[plan.plan_name] ? (
                  <p className="mt-2 text-xs text-destructive">{errors[plan.plan_name]}</p>
                ) : null}
              </div>
            );
          })}
        </div>

        {loadingSubs ? (
          <p className="mt-6 text-sm text-muted-foreground">載入訂閱狀態中…</p>
        ) : null}
      </main>
    </div>
  );
}
