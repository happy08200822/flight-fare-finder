import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Plane, BellRing, CalendarX2 } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Flight Price Notifier — 機票降價通知" },
      {
        name: "description",
        content:
          "設定航線與目標價，機票降價就通知你。Set a route and a target price — we email you when the fare drops.",
      },
      { property: "og:title", content: "Flight Price Notifier — 機票降價通知" },
      {
        property: "og:description",
        content: "Set a route and a target price — we email you when the fare drops.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Landing,
});

function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry && entry.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`transition-all duration-700 ease-out ${
        shown ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
      }`}
    >
      {children}
    </div>
  );
}

const features = [
  {
    icon: Plane,
    title: "盯緊熱門航線",
    en: "Always-on route watching",
    body: "持續監控台北出發的熱門航線（東京、首爾），自動抓最低票價。",
  },
  {
    icon: BellRing,
    title: "達標自動通知",
    en: "Target-price email alerts",
    body: "低於你設定的目標價，就寄 email 提醒你，附上立即訂購連結。",
  },
  {
    icon: CalendarX2,
    title: "隨時取消",
    en: "Cancel anytime",
    body: "月訂閱制，不想用隨時停，沒有綁約。",
  },
];

function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <span className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid size-7 place-items-center rounded-lg bg-primary/15 text-primary">
              <Plane className="size-4" />
            </span>
            Flight Price Notifier
          </span>
          <Link
            to="/auth"
            className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-[0_0_30px_-8px_var(--primary)] transition hover:opacity-90"
          >
            Sign in / 登入
          </Link>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden">
          <div className="pointer-events-none absolute -top-40 left-1/2 size-[42rem] -translate-x-1/2 rounded-full bg-primary/20 blur-[120px]" />
          <div className="relative mx-auto max-w-4xl px-5 py-28 text-center sm:py-36">
            <Reveal>
              <p className="mb-5 inline-flex rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
                台北出發 · 東京 · 首爾
              </p>
              <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
                Flight Price Notifier
              </h1>
              <p className="mx-auto mt-6 max-w-2xl text-xl font-medium sm:text-2xl">
                設定航線與目標價，機票降價就通知你
              </p>
              <p className="mx-auto mt-3 max-w-xl text-base text-muted-foreground">
                Set a route and a target price — we email you when the fare drops.
              </p>
              <div className="mt-10">
                <Link
                  to="/auth"
                  className="inline-flex rounded-full bg-primary px-7 py-3 text-base font-medium text-primary-foreground shadow-[0_0_50px_-12px_var(--primary)] transition hover:opacity-90"
                >
                  Sign in / 登入
                </Link>
              </div>
            </Reveal>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-5 pb-28">
          <div className="grid gap-6 md:grid-cols-3">
            {features.map((f, i) => (
              <Reveal key={f.en} delay={i * 120}>
                <article className="h-full rounded-2xl border border-border bg-card p-7 transition hover:border-primary/50">
                  <span className="mb-5 grid size-11 place-items-center rounded-xl bg-primary/15 text-primary">
                    <f.icon className="size-5" />
                  </span>
                  <h2 className="text-lg font-semibold">{f.title}</h2>
                  <p className="mt-1 text-sm text-primary/80">{f.en}</p>
                  <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
                </article>
              </Reveal>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-border/60">
        <div className="mx-auto max-w-6xl px-5 py-8 text-sm text-muted-foreground">
          © 2026 Flight Price Notifier
        </div>
      </footer>
    </div>
  );
}
