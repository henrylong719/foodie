import Link from "next/link";
import { getOrder } from "@/lib/api";
import {
  Card,
  ErrorNote,
  PageContent,
  PageHeader,
  SectionTitle,
  StatusBadge,
  cx,
} from "@/components/ui";
import type { OrderItem } from "@/lib/types";

export const dynamic = "force-dynamic";

const orderDateFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Australia/Sydney",
  timeZoneName: "short",
});

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return orderDateFormatter.format(new Date(iso));
}

function formatSource(source: string): string {
  const labels: Record<string, string> = {
    history: "from history",
    mentioned: "customer said",
    recommended: "recommended",
  };
  return labels[source] ?? source.replace(/_/g, " ");
}

function sourceTone(source: string): string {
  if (source === "recommended") {
    return "border-[color:rgba(184,107,23,0.22)] bg-[color:rgba(184,107,23,0.08)] text-[var(--color-warn)]";
  }
  if (source === "history") {
    return "border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)] text-[var(--color-good)]";
  }
  return "border-[color:rgba(32,35,31,0.14)] bg-[color:rgba(32,35,31,0.04)] text-[var(--color-text)]";
}

function getReviewNote(item: OrderItem): string {
  if (item.brand_source === "recommended") {
    return "Verify against the call or catalog before fulfillment.";
  }
  if (item.brand_source === "mentioned") {
    return "Customer explicitly named this brand.";
  }
  return "Matched from customer history.";
}

function countItemsBySource(
  items: OrderItem[],
  source: OrderItem["brand_source"],
) {
  return items.filter((item) => item.brand_source === source).length;
}

export default async function OrderDetailPage({
  params,
}: {
  params: Promise<{ orderId: string }>;
}) {
  const { orderId } = await params;

  try {
    const order = await getOrder(orderId);
    const recommendedCount = countItemsBySource(order.items, "recommended");
    const mentionedCount = countItemsBySource(order.items, "mentioned");
    const historyCount = countItemsBySource(order.items, "history");

    return (
      <div>
        <PageHeader
          title="Order Review"
          subtitle={`${order.customer_name} - ${formatDate(order.created_at)}`}
        />

        <PageContent className="space-y-6">
          <Card className="overflow-hidden">
            <div className="grid gap-4 px-4 py-4 sm:px-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-lg font-semibold text-[var(--color-text)]">
                    {order.customer_name}
                  </h2>
                  <StatusBadge status={order.status} />
                </div>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--color-text-dim)]">
                  <span>{order.item_count} item{order.item_count === 1 ? "" : "s"}</span>
                  <span>{recommendedCount} AI pick{recommendedCount === 1 ? "" : "s"}</span>
                  <span>{mentionedCount} said</span>
                  <span>{historyCount} history</span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <Link
                  href="/orders"
                  className="inline-flex h-9 items-center rounded-full border bg-white px-4 text-xs font-semibold text-[var(--color-text-dim)] transition hover:border-[color:rgba(33,122,74,0.3)] hover:text-[var(--color-accent)]"
                >
                  Back to queue
                </Link>
                <Link
                  href={`/calls/${order.call_id}`}
                  className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                >
                  Review call
                </Link>
              </div>
            </div>
          </Card>

          <section>
            <SectionTitle
              title="Line items"
              subtitle="Use this page for exact item verification; keep the queue for triage."
            />
            <Card className="overflow-hidden">
              <div className="overflow-x-auto [scrollbar-gutter:stable]">
                <div className="min-w-[820px]">
                  <div className="grid grid-cols-[72px_minmax(260px,1fr)_170px_minmax(260px,1fr)] gap-4 border-b bg-[var(--color-surface-2)] px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-dim)]">
                    <span>Qty</span>
                    <span>Item</span>
                    <span>Source</span>
                    <span>Review note</span>
                  </div>
                  {order.items.map((item, i) => (
                    <div
                      key={`${item.product_id}-${i}`}
                      className={cx(
                        "grid grid-cols-[72px_minmax(260px,1fr)_170px_minmax(260px,1fr)] items-center gap-4 border-t px-5 py-4 text-sm transition first:border-t-0 hover:bg-[color:rgba(241,245,238,0.72)]",
                        item.brand_source === "recommended" &&
                          "bg-[color:rgba(184,107,23,0.035)]",
                      )}
                    >
                      <span
                        className="flex h-8 w-12 items-center justify-center rounded-lg bg-[color:rgba(33,122,74,0.08)] font-semibold text-[var(--color-accent)]"
                        style={{ fontFamily: "var(--font-mono)" }}
                      >
                        x{item.quantity}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-[var(--color-text)]">
                          {item.name}
                        </span>
                        <span
                          className="mt-0.5 block truncate text-xs text-[var(--color-text-dim)]"
                          style={{ fontFamily: "var(--font-mono)" }}
                        >
                          {item.product_id}
                        </span>
                      </span>
                      <span
                        className={cx(
                          "inline-flex w-fit rounded-full border px-2.5 py-1 text-[11px] font-semibold",
                          sourceTone(item.brand_source),
                        )}
                        style={{ fontFamily: "var(--font-mono)" }}
                      >
                        {formatSource(item.brand_source)}
                      </span>
                      <span className="text-xs leading-5 text-[var(--color-text-dim)]">
                        {getReviewNote(item)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          </section>
        </PageContent>
      </div>
    );
  } catch (e) {
    return (
      <div>
        <PageHeader title="Order Review" />
        <ErrorNote message={(e as Error).message} />
      </div>
    );
  }
}
