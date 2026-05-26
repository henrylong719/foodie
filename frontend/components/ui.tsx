import type { ReactNode } from "react";

// Small presentational components shared across pages.

export function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatStatus(status: string) {
  return status.replace(/[_-]/g, " ");
}

export function StatusBadge({
  status,
  children,
  className,
}: {
  status: string;
  children?: ReactNode;
  className?: string;
}) {
  const normalized = status.toLowerCase().replace(/\s+/g, "_");
  const map: Record<string, string> = {
    active:
      "text-[var(--color-accent)] border-[color:rgba(15,118,110,0.2)] bg-[color:rgba(15,118,110,0.08)]",
    callable:
      "text-[var(--color-good)] border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)]",
    completed:
      "text-[var(--color-good)] border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)]",
    confirmed:
      "text-[var(--color-good)] border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)]",
    ended:
      "text-[var(--color-good)] border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)]",
    fulfilled:
      "text-[var(--color-good)] border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)]",
    in_stock:
      "text-[var(--color-good)] border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)]",
    "in-stock":
      "text-[var(--color-good)] border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)]",
    pending:
      "text-[var(--color-warn)] border-[color:rgba(184,107,23,0.22)] bg-[color:rgba(184,107,23,0.08)]",
    pending_fulfillment:
      "text-[var(--color-warn)] border-[color:rgba(184,107,23,0.22)] bg-[color:rgba(184,107,23,0.08)]",
    queued:
      "text-[var(--color-warn)] border-[color:rgba(184,107,23,0.22)] bg-[color:rgba(184,107,23,0.08)]",
    waiting:
      "text-[var(--color-warn)] border-[color:rgba(184,107,23,0.22)] bg-[color:rgba(184,107,23,0.08)]",
    blocked:
      "text-[var(--color-danger)] border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)]",
    cancelled:
      "text-[var(--color-danger)] border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)]",
    do_not_call:
      "text-[var(--color-danger)] border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)]",
    "do-not-call":
      "text-[var(--color-danger)] border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)]",
    failed:
      "text-[var(--color-danger)] border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)]",
    out_of_stock:
      "text-[var(--color-danger)] border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)]",
    "out-of-stock":
      "text-[var(--color-danger)] border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)]",
  };
  const cls =
    map[normalized] ??
    "text-[var(--color-text-dim)] border-[var(--color-border-strong)] bg-[var(--color-surface-2)]";
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.04em]",
        cls,
        className,
      )}
    >
      {children ?? formatStatus(status)}
    </span>
  );
}

// Shows HOW an item's brand was decided — the project's signature detail.
export function BrandSourceTag({ source }: { source: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    history: {
      label: "from history",
      cls: "text-[var(--color-good)]",
    },
    mentioned: {
      label: "customer said",
      cls: "text-[var(--color-text)]",
    },
    recommended: {
      label: "recommended",
      cls: "text-[var(--color-accent)]",
    },
  };
  const m = map[source] ?? {
    label: source,
    cls: "text-[var(--color-text-dim)]",
  };
  return (
    <span
      className={`rounded-full border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-0.5 text-[11px] ${m.cls}`}
      style={{ fontFamily: "var(--font-mono)" }}
    >
      {m.label}
    </span>
  );
}

export function StockDot({ inStock }: { inStock: boolean }) {
  return (
    <span
      className="mt-1.5 inline-block h-2.5 w-2.5 rounded-full ring-4 ring-[var(--color-surface-2)]"
      style={{
        background: inStock ? "var(--color-good)" : "var(--color-danger)",
      }}
      title={inStock ? "in stock" : "out of stock"}
    />
  );
}

export function PageContent({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="border-b bg-[color:rgba(255,255,255,0.76)] backdrop-blur-xl">
      <div className="mx-auto w-full max-w-6xl px-4 pb-6 pt-7 sm:px-6 sm:pt-8 lg:px-8 lg:pb-8 lg:pt-9">
        <div className="flex max-w-3xl flex-col gap-2.5">
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-accent)]">
            Foodie operations
          </span>
          <h1 className="text-[2rem] font-semibold leading-[1.08] text-[var(--color-text)] sm:text-[2.4rem]">
            {title}
          </h1>
          {subtitle && (
            <p className="max-w-2xl text-[15px] leading-7 text-[var(--color-text-dim)]">
              {subtitle}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-2xl border bg-[color:rgba(255,255,255,0.92)] shadow-[0_1px_2px_rgba(16,35,33,0.04),0_14px_34px_rgba(16,35,33,0.055)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="text-sm font-semibold text-[var(--color-text)]">
          {title}
        </h2>
        {subtitle && (
          <p className="mt-1 text-xs leading-5 text-[var(--color-text-dim)]">
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
  className,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-2xl border border-dashed bg-[color:rgba(255,255,255,0.78)] px-5 py-8 text-sm shadow-sm",
        className,
      )}
    >
      <div className="flex gap-4">
        <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border bg-[var(--color-surface-2)]">
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-accent)]" />
        </span>
        <div className="min-w-0">
          <div className="font-semibold text-[var(--color-text)]">{title}</div>
          {children && (
            <div className="mt-1 max-w-2xl leading-6 text-[var(--color-text-dim)]">
              {children}
            </div>
          )}
          {action && <div className="mt-4">{action}</div>}
        </div>
      </div>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cx(
        "animate-pulse rounded-md bg-[color:rgba(32,35,31,0.07)]",
        className,
      )}
    />
  );
}

export function ErrorNote({ message }: { message: string }) {
  const is404 = message.includes("404");
  const isConn =
    message.includes("fetch") || message.includes("ECONNREFUSED");

  let hint: string;
  if (is404) {
    hint =
      "The backend is reachable but this route does not exist. " +
      "Check that the backend version exposes the list endpoints.";
  } else if (isConn) {
    hint =
      "Could not reach the backend. Is it running at the configured " +
      "NEXT_PUBLIC_API_BASE?";
  } else {
    hint = "The backend returned an unexpected error.";
  }

  return (
    <div className="m-4 rounded-2xl border border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)] p-4 text-sm text-[var(--color-danger)] shadow-sm sm:m-6 lg:m-10">
      <div className="font-medium">{message}</div>
      <div className="text-[var(--color-text-dim)] mt-1">{hint}</div>
    </div>
  );
}
