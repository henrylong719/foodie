import Link from "next/link";
import { listOrders } from "@/lib/api";
import {
  Card,
  EmptyState,
  ErrorNote,
  PageContent,
  PageHeader,
  SectionTitle,
  StatusBadge,
  cx,
} from "@/components/ui";
import type { CapturedOrder, OrderItem } from "@/lib/types";

export const dynamic = "force-dynamic";

const orderDateFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
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

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "CU";
  return parts
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function countItemsBySource(
  items: OrderItem[],
  source: OrderItem["brand_source"],
) {
  return items.filter((item) => item.brand_source === source).length;
}

function countOrdersWithRecommendedItems(orders: CapturedOrder[]) {
  return orders.filter((order) =>
    order.items.some((item) => item.brand_source === "recommended"),
  ).length;
}

function countOrdersByStatus(orders: CapturedOrder[], status: string) {
  return orders.filter((order) => order.status === status).length;
}

function OrderMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <div className="rounded-xl border bg-[color:rgba(255,255,255,0.74)] p-4">
      <div className="text-xs font-medium text-[var(--color-text-dim)]">
        {label}
      </div>
      <div
        className="mt-2 text-3xl font-semibold leading-none text-[var(--color-text)]"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        {value}
      </div>
      <div className="mt-3 border-t pt-2 text-xs text-[var(--color-text-dim)]">
        {detail}
      </div>
    </div>
  );
}

function SourcePill({
  source,
  className,
}: {
  source: string;
  className?: string;
}) {
  const tone =
    source === "recommended"
      ? "border-[color:rgba(184,107,23,0.22)] bg-[color:rgba(184,107,23,0.08)] text-[var(--color-warn)]"
      : source === "history"
        ? "border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)] text-[var(--color-good)]"
        : "border-[color:rgba(32,35,31,0.14)] bg-[color:rgba(32,35,31,0.04)] text-[var(--color-text)]";

  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold",
        tone,
        className,
      )}
      style={{ fontFamily: "var(--font-mono)" }}
    >
      {formatSource(source)}
    </span>
  );
}

function OrderItemPreview({ item }: { item: OrderItem }) {
  return (
    <div
      className={cx(
        "flex min-w-0 items-center gap-3 rounded-xl border bg-white px-3 py-2.5",
        item.brand_source === "recommended" &&
          "border-[color:rgba(184,107,23,0.22)] bg-[color:rgba(184,107,23,0.05)]",
      )}
    >
      <span
        className="flex h-7 w-10 shrink-0 items-center justify-center rounded-lg bg-[color:rgba(33,122,74,0.08)] text-xs font-semibold text-[var(--color-accent)]"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        x{item.quantity}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-[var(--color-text)]">
          {item.name}
        </span>
        <span className="mt-1 block">
          <SourcePill source={item.brand_source} className="py-0.5" />
        </span>
      </span>
    </div>
  );
}

function OrderCard({ order }: { order: CapturedOrder }) {
  const historyCount = countItemsBySource(order.items, "history");
  const mentionedCount = countItemsBySource(order.items, "mentioned");
  const recommendedCount = countItemsBySource(order.items, "recommended");
  const needsReview = recommendedCount > 0;
  const previewItems = order.items.slice(0, 3);
  const remainingCount = Math.max(order.items.length - previewItems.length, 0);
  const sourceSummary: string[] = [];
  if (mentionedCount > 0) sourceSummary.push(`${mentionedCount} said`);
  if (historyCount > 0) sourceSummary.push(`${historyCount} history`);
  if (recommendedCount > 0) {
    sourceSummary.push(
      `${recommendedCount} AI pick${recommendedCount === 1 ? "" : "s"}`,
    );
  }

  return (
    <Card
      className={cx(
        "overflow-hidden transition hover:border-[color:rgba(33,122,74,0.24)]",
        needsReview && "border-[color:rgba(184,107,23,0.24)]",
      )}
    >
      <div className="grid gap-4 border-b bg-[var(--color-surface-2)] px-4 py-4 sm:px-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="flex min-w-0 gap-3 sm:gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-xs font-semibold text-[var(--color-accent)] shadow-sm">
            {getInitials(order.customer_name)}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <h3 className="truncate text-base font-semibold text-[var(--color-text)]">
                {order.customer_name}
              </h3>
              <StatusBadge status={order.status} />
            </div>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--color-text-dim)]">
              <span>{formatDate(order.created_at)}</span>
              <span
                className="font-medium text-[var(--color-text)]"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {order.item_count} item{order.item_count === 1 ? "" : "s"}
              </span>
              <span>
                {needsReview
                  ? `${recommendedCount} AI recommendation${recommendedCount === 1 ? "" : "s"} to review`
                  : "All brands tied to shopper signal"}
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          {sourceSummary.map((summary) => (
            <span
              key={summary}
              className="rounded-full border bg-white px-3 py-1 text-xs font-medium text-[var(--color-text-dim)]"
            >
              {summary}
            </span>
          ))}
          <Link
            href={`/orders/${order._id}`}
            className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-white px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:-translate-y-px hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
          >
            View order
          </Link>
        </div>
      </div>

      <div className="px-4 py-4 sm:px-5">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {previewItems.map((item, i) => (
            <OrderItemPreview
              key={`${item.product_id}-preview-${i}`}
              item={item}
            />
          ))}
          {remainingCount > 0 && (
            <Link
              href={`/orders/${order._id}`}
              className="flex min-h-[74px] items-center justify-center rounded-xl border border-dashed bg-[color:rgba(255,255,255,0.62)] px-3 py-2.5 text-sm font-semibold text-[var(--color-accent)] transition hover:border-[color:rgba(33,122,74,0.3)] hover:bg-white"
            >
              +{remainingCount} more item{remainingCount === 1 ? "" : "s"}
            </Link>
          )}
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-3">
          <span className="text-xs text-[var(--color-text-dim)]">
            Exact item review, product IDs, and fulfillment notes are on the
            order page.
          </span>
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/calls/${order.call_id}`}
              className="inline-flex h-9 items-center rounded-full border bg-white px-4 text-xs font-semibold text-[var(--color-text-dim)] transition hover:border-[color:rgba(33,122,74,0.3)] hover:text-[var(--color-accent)]"
            >
              Call
            </Link>
            <Link
              href={`/orders/${order._id}`}
              className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
            >
              Review items
            </Link>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default async function OrdersPage() {
  try {
    const { orders, count } = await listOrders();
    const recommendedOrders = countOrdersWithRecommendedItems(orders);
    const pendingOrders =
      countOrdersByStatus(orders, "pending_fulfillment") +
      countOrdersByStatus(orders, "pending_fulfilment");
    const totalItems = orders.reduce((sum, order) => sum + order.item_count, 0);

    return (
      <div>
        <PageHeader
          title="Captured Orders"
          subtitle="Review voice-captured grocery orders, confirm AI brand choices, and move clean orders toward fulfillment."
        />

        <PageContent className="space-y-6">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <OrderMetric
              label="Captured"
              value={count}
              detail={`${totalItems} total item${totalItems === 1 ? "" : "s"}`}
            />
            <OrderMetric
              label="Needs review"
              value={recommendedOrders}
              detail="Orders with AI-recommended brands"
            />
            <OrderMetric
              label="Pending"
              value={pendingOrders}
              detail="Waiting on fulfillment workflow"
            />
          </div>

          <SectionTitle
            title="Review queue"
            subtitle="Recommended brand choices are highlighted because they carry the most operational risk."
          />
          {orders.length === 0 ? (
            <EmptyState
              title="No orders captured yet"
              action={
                <Link
                  href="/customers"
                  className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                >
                  View customers
                </Link>
              }
            >
              Each completed call writes one order here, with every item,
              quantity, and how its brand was decided.
            </EmptyState>
          ) : (
            <div className="space-y-4">
              {orders.map((order) => (
                <OrderCard key={order._id} order={order} />
              ))}
            </div>
          )}
        </PageContent>
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
