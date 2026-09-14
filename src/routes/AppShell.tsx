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
  subscription_status?: "pending_payment" | "active" | "cancelled" | "expired";
  current_period_end?: string;
};

// Legacy (pre-M2) rows have no subscription_status at all — treat them the same
// as pending_payment: they keep the user's chosen target price, but need a
// payment before they get alerts again.
function statusOf(sub: Subscription | undefined) {
  return sub?.subscription_status ?? (sub ? "pending_payment" : undefined);
}

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

  async function refreshSubs() {
    const data = await fetch(
      `${API_BASE}/subscriptions?email=${encodeURIComponent(email)}`,
    ).then((r) => r.json());
    setSubs(data.items ?? []);
  }

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

  async function subscribe(planName: string, prefillTarget?: number) {
    const raw = drafts[planName];
    const targetPrice = raw ? Number(raw) : prefillTarget;
    if (!targetPrice || !Number.isFinite(targetPrice) || targetPrice <= 0) {
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

      const contentType = res.headers.get("content-type") ?? "";
      if (contentType.includes("text/html")) {
        // A checkout is needed — hand the browser to ECPay's auto-submit form.
        const html = await res.text();
        document.open();
        document.write(html);
        document.close();
        return;
      }

      // In-place update (active/cancelled-in-grace) — no payment, just refresh.
      await refreshSubs();
      setDrafts((d) => ({ ...d, [planName]: "" }));
    } catch {
      setErrors((e) => ({ ...e, [planName]: "操作失敗，請稍後再試" }));
    } finally {
      setSaving(null);
    }
  }

  async function cancelSubscription(route: string, planName: string) {
    setSaving(planName);
    try {
      const res = await fetch(`${API_BASE}/cancel`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, route }),
      });
      if (!res.ok) throw new Error("cancel failed");
      await refreshSubs();
    } catch {
      setErrors((e) => ({ ...e, [planName]: "取消失敗，請稍後再試" }));
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
          選一條航線、設定目標價，機票降到目標價我們就寄信通知你（月費 NT$300）。
        </p>

        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          {PLANS.map((plan) => {
            const sub = subs.find((s) => s.plan_name === plan.plan_name);
            const status = statusOf(sub);
            const isSaving = saving === plan.plan_name;
            const periodEndDate = sub?.current_period_end?.slice(0, 10);

            const badge =
              status === "active" ? (
                <span className="flex items-center gap-1 rounded-full bg-primary/15 px-3 py-1 text-xs font-medium text-primary">
                  <BellRing className="size-3" />
                  已訂閱（有效）
                </span>
              ) : status === "pending_payment" ? (
                <span className="rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-foreground">
                  未完成付款
                </span>
              ) : status === "cancelled" ? (
                <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
                  已取消 · 有效至 {periodEndDate}
                </span>
              ) : status === "expired" ? (
                <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
                  已結束
                </span>
              ) : null;

            const buttonLabel = isSaving
              ? "處理中…"
              : status === "active" || status === "cancelled"
                ? "更新目標價"
                : status === "pending_payment"
                  ? "完成付款"
                  : status === "expired"
                    ? "重新訂閱"
                    : "開始追蹤";

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
                  {badge}
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
                    onClick={() => subscribe(plan.plan_name, sub?.target_price)}
                    disabled={isSaving}
                    className="shrink-0 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-60"
                  >
                    {buttonLabel}
                  </button>
                </div>

                {status === "active" ? (
                  <button
                    type="button"
                    onClick={() => sub && cancelSubscription(sub.route, plan.plan_name)}
                    disabled={isSaving}
                    className="mt-3 text-xs text-muted-foreground underline-offset-2 transition hover:text-destructive hover:underline disabled:opacity-60"
                  >
                    取消訂閱
                  </button>
                ) : null}

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
