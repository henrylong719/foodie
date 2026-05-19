import { listOrders } from "@/lib/api";
import {
  PageHeader,
  ErrorNote,
  StatusBadge,
  BrandSourceTag,
} from "@/components/ui";

export const dynamic = "force-dynamic";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default async function OrdersPage() {
  try {
    const { orders, count } = await listOrders();

    return (
      <div>
        <PageHeader
          title="Captured Orders"
          subtitle={`${count} orders captured from completed calls`}
        />

        <div className="px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
          {orders.length === 0 ? (
            <p className="rounded-2xl border border-dashed bg-[color:rgba(255,255,255,0.72)] px-5 py-8 text-sm leading-6 text-[var(--color-text-dim)] shadow-sm">
              No orders captured yet. Each completed call writes one order
              here, with every item, quantity, and how its brand was decided.
            </p>
          ) : (
            <div className="space-y-4">
              {orders.map((o) => (
                <div
                  key={o._id}
                  className="overflow-hidden rounded-2xl border bg-[color:rgba(255,255,255,0.86)] shadow-sm"
                >
                  <div className="flex flex-wrap items-center gap-3 border-b bg-[var(--color-surface-2)] px-4 py-4 sm:gap-4 sm:px-5">
                    <span className="min-w-0 flex-1 text-sm font-medium text-[var(--color-text)]">
                      {o.customer_name}
                    </span>
                    <span className="text-xs text-[var(--color-text-dim)]">
                      {formatDate(o.created_at)}
                    </span>
                    <StatusBadge status={o.status} />
                  </div>

                  <div>
                    {o.items.map((item, i) => (
                      <div
                        key={i}
                        className={`flex items-center gap-3 px-4 py-3.5 text-sm transition hover:bg-[var(--color-surface-2)] sm:gap-4 sm:px-5 ${
                          i > 0 ? "border-t" : ""
                        }`}
                      >
                        <span
                          className="w-10 shrink-0 font-semibold text-[var(--color-accent)]"
                          style={{ fontFamily: "var(--font-mono)" }}
                        >
                          ×{item.quantity}
                        </span>
                        <span className="min-w-0 flex-1 text-[var(--color-text)]">
                          {item.name}
                        </span>
                        <BrandSourceTag source={item.brand_source} />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  } catch (e) {
    return (
      <div>
        <PageHeader title="Captured Orders" />
        <ErrorNote message={(e as Error).message} />
      </div>
    );
  }
}
