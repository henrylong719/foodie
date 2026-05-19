import Link from "next/link";
import { listOrders, listCustomers, listProducts } from "@/lib/api";
import { PageHeader, ErrorNote, StatusBadge } from "@/components/ui";

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

  const stats = [
    {
      label: "Captured orders",
      value: orders?.count ?? "—",
      href: "/orders",
    },
    {
      label: "Customers",
      value: customers?.count ?? "—",
      href: "/customers",
    },
    { label: "Callable now", value: customers ? callable : "—", href: "/customers" },
    {
      label: "Catalog items",
      value: products?.count ?? "—",
      href: "/catalog",
    },
  ];

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Outbound AI sales assistant — current state"
      />

      <div className="grid grid-cols-1 gap-4 px-4 py-6 sm:grid-cols-2 sm:px-6 lg:grid-cols-4 lg:px-10 lg:py-8">
        {stats.map((s) => (
          <Link
            key={s.label}
            href={s.href}
            className="group rounded-2xl border bg-[color:rgba(255,255,255,0.86)] p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-[color:rgba(15,118,110,0.26)] hover:shadow-md"
          >
            <div
              className="text-4xl font-semibold leading-none tracking-[-0.04em] text-[var(--color-text)] transition group-hover:text-[var(--color-accent)]"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {s.value}
            </div>
            <div className="mt-3 text-sm font-medium text-[var(--color-text-dim)]">
              {s.label}
            </div>
          </Link>
        ))}
      </div>

      <div className="px-4 pb-10 sm:px-6 lg:px-10 lg:pb-12">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-dim)]">
          Recent captured orders
        </h2>
        {recent.length === 0 ? (
          <p className="rounded-2xl border border-dashed bg-[color:rgba(255,255,255,0.72)] px-5 py-8 text-sm text-[var(--color-text-dim)] shadow-sm">
            No orders captured yet. Orders appear here once calls complete.
          </p>
        ) : (
          <div className="overflow-hidden rounded-2xl border bg-[color:rgba(255,255,255,0.84)] shadow-sm">
            {recent.map((o, i) => (
              <Link
                key={o._id}
                href={`/orders`}
                className={`flex items-center gap-4 px-4 py-4 text-sm transition hover:bg-[var(--color-surface-2)] sm:px-5 ${
                  i > 0 ? "border-t" : ""
                }`}
              >
                <span className="min-w-0 flex-1 truncate font-medium text-[var(--color-text)]">
                  {o.customer_name}
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
          </div>
        )}
      </div>
    </div>
  );
}
