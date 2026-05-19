import Link from "next/link";
import { listOrders, listCustomers, listProducts } from "@/lib/api";
import {
  Card,
  EmptyState,
  ErrorNote,
  PageContent,
  PageHeader,
  SectionTitle,
  StatusBadge,
} from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  // Resilient: one failing endpoint degrades only its own stat, not the page.
  const [ordersR, customersR, productsR] = await Promise.allSettled([
    listOrders(),
    listCustomers(),
    listProducts(),
  ]);

  const orders = ordersR.status === "fulfilled" ? ordersR.value : null;
  const customers =
    customersR.status === "fulfilled" ? customersR.value : null;
  const products = productsR.status === "fulfilled" ? productsR.value : null;

  // Only show the full error state if everything failed (backend down).
  if (!orders && !customers && !products) {
    const msg =
      ordersR.status === "rejected"
        ? (ordersR.reason as Error).message
        : "Backend unreachable";
    return (
      <div>
        <PageHeader title="Overview" />
        <ErrorNote message={msg} />
      </div>
    );
  }

  const recent = orders?.orders.slice(0, 6) ?? [];
  const callable =
    customers?.customers.filter((c) => !c.do_not_call).length ?? 0;
  const doNotCall =
    customers?.customers.filter((c) => c.do_not_call).length ?? 0;
  const inStock = products?.products.filter((p) => p.in_stock).length ?? 0;
  const outOfStock = products ? products.count - inStock : 0;
  const stockRate =
    products && products.count > 0
      ? Math.round((inStock / products.count) * 100)
      : null;

  const stats = [
    {
      label: "Captured orders",
      value: orders?.count ?? "—",
      href: "/orders",
      detail: "Ready for review",
      accent: "bg-[var(--color-accent)]",
    },
    {
      label: "Customers",
      value: customers?.count ?? "—",
      href: "/customers",
      detail: "Known shoppers",
      accent: "bg-[var(--color-warn)]",
    },
    {
      label: "Callable now",
      value: customers ? callable : "—",
      href: "/customers",
      detail: "Eligible contacts",
      accent: "bg-[var(--color-good)]",
    },
    {
      label: "Catalog items",
      value: products?.count ?? "—",
      href: "/catalog",
      detail: "Resolvable products",
      accent: "bg-[var(--color-text)]",
    },
  ];

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Monitor Foodie's AI voice ordering workflow across shoppers, calls, captured orders, and catalog readiness."
      />

      <PageContent className="space-y-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {stats.map((s) => (
            <Link
              key={s.label}
              href={s.href}
              className="group rounded-2xl border bg-[color:rgba(255,255,255,0.92)] p-5 shadow-[0_1px_2px_rgba(32,35,31,0.04),0_14px_34px_rgba(32,35,31,0.055)] transition hover:-translate-y-0.5 hover:border-[color:rgba(33,122,74,0.24)] hover:shadow-[0_1px_2px_rgba(32,35,31,0.06),0_18px_40px_rgba(32,35,31,0.075)]"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-[var(--color-text-dim)]">
                    {s.label}
                  </div>
                  <div
                    className="mt-3 text-4xl font-semibold leading-none text-[var(--color-text)] transition group-hover:text-[var(--color-accent)]"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {s.value}
                  </div>
                </div>
                <span className={`mt-1 h-2.5 w-2.5 rounded-full ${s.accent}`} />
              </div>
              <div className="mt-4 border-t pt-3 text-xs font-medium text-[var(--color-text-dim)]">
                {s.detail}
              </div>
            </Link>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
          <section>
            <SectionTitle
              title="Recent captured orders"
              subtitle="Latest order records created by completed assistant calls."
            />
            {recent.length === 0 ? (
              <EmptyState
                title="No orders captured yet"
                action={
                  <Link
                    href="/customers"
                    className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                  >
                    View callable customers
                  </Link>
                }
              >
                Completed calls will populate this list with shopper name,
                item count, and order status.
              </EmptyState>
            ) : (
              <Card className="overflow-hidden">
                {recent.map((o, i) => (
                  <Link
                    key={o._id}
                    href={`/orders`}
                    className={`flex items-center gap-4 px-4 py-4 text-sm transition hover:bg-[var(--color-surface-2)] sm:px-5 ${
                      i > 0 ? "border-t" : ""
                    }`}
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--color-surface-2)] text-xs font-semibold text-[var(--color-accent)]">
                      {o.customer_name.slice(0, 2).toUpperCase()}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-[var(--color-text)]">
                        {o.customer_name}
                      </span>
                      <span className="mt-0.5 block text-xs text-[var(--color-text-dim)] sm:hidden">
                        {o.item_count} item{o.item_count === 1 ? "" : "s"}
                      </span>
                    </span>
                    <span
                      className="hidden text-[var(--color-text-dim)] sm:inline"
                      style={{ fontFamily: "var(--font-mono)" }}
                    >
                      {o.item_count} item{o.item_count === 1 ? "" : "s"}
                    </span>
                    <StatusBadge status={o.status} />
                  </Link>
                ))}
              </Card>
            )}
          </section>

          <section>
            <SectionTitle
              title="Operations readiness"
              subtitle="A quick read on outreach and catalog quality."
            />
            <Card className="overflow-hidden">
              <div className="space-y-4 p-5">
                <ReadinessRow
                  label="Callable customers"
                  value={customers ? `${callable}` : "—"}
                  detail={
                    customers
                      ? `${doNotCall} marked do-not-call`
                      : "Customer endpoint unavailable"
                  }
                  tone="good"
                />
                <ReadinessRow
                  label="Catalog in stock"
                  value={stockRate === null ? "—" : `${stockRate}%`}
                  detail={
                    products
                      ? `${outOfStock} products out of stock`
                      : "Catalog endpoint unavailable"
                  }
                  tone={outOfStock > 0 ? "warn" : "good"}
                />
                <ReadinessRow
                  label="Recent call activity"
                  value="Live"
                  detail="Open a call detail page to monitor streaming transcripts."
                  tone="neutral"
                />
              </div>
              <div className="border-t bg-[var(--color-surface-2)] px-5 py-4">
                <Link
                  href="/catalog"
                  className="text-sm font-semibold text-[var(--color-accent)] transition hover:text-[var(--color-text)]"
                >
                  Review catalog readiness
                </Link>
              </div>
            </Card>
          </section>
        </div>
      </PageContent>
    </div>
  );
}

function ReadinessRow({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "good" | "warn" | "neutral";
}) {
  const toneClass = {
    good: "bg-[color:rgba(31,122,61,0.1)] text-[var(--color-good)]",
    warn: "bg-[color:rgba(180,107,25,0.1)] text-[var(--color-warn)]",
    neutral: "bg-[var(--color-surface-2)] text-[var(--color-text-dim)]",
  }[tone];

  return (
    <div className="flex items-center gap-4">
      <span
        className={`flex h-11 w-14 shrink-0 items-center justify-center rounded-2xl text-sm font-semibold ${toneClass}`}
        style={{ fontFamily: "var(--font-mono)" }}
      >
        {value}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-[var(--color-text)]">
          {label}
        </span>
        <span className="mt-0.5 block text-xs leading-5 text-[var(--color-text-dim)]">
          {detail}
        </span>
      </span>
    </div>
  );
}
