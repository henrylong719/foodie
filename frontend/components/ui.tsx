// Small presentational components shared across pages.

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending_fulfilment:
      "text-[var(--color-warn)] border-[color:rgba(184,107,23,0.24)] bg-[color:rgba(184,107,23,0.09)]",
    fulfilled:
      "text-[var(--color-good)] border-[color:rgba(21,128,61,0.2)] bg-[color:rgba(21,128,61,0.08)]",
  };
  const cls =
    map[status] ??
    "text-[var(--color-text-dim)] border-[var(--color-border-strong)] bg-[var(--color-surface-2)]";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${cls}`}
    >
      {status.replace(/_/g, " ")}
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
      className={`rounded-full bg-[var(--color-surface-2)] px-2 py-0.5 text-[11px] ${m.cls}`}
      style={{ fontFamily: "var(--font-mono)" }}
    >
      {m.label}
    </span>
  );
}

export function StockDot({ inStock }: { inStock: boolean }) {
  return (
    <span
      className="mt-1.5 inline-block h-2 w-2 rounded-full ring-4 ring-[var(--color-surface-2)]"
      style={{
        background: inStock ? "var(--color-good)" : "var(--color-danger)",
      }}
      title={inStock ? "in stock" : "out of stock"}
    />
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
    <div className="border-b bg-[color:rgba(255,255,255,0.72)] px-4 pb-6 pt-7 backdrop-blur-xl sm:px-6 sm:pt-9 lg:px-10 lg:pb-8 lg:pt-10">
      <h1
        className="text-3xl font-semibold leading-tight tracking-[-0.02em] text-[var(--color-text)]"
      >
        {title}
      </h1>
      {subtitle && (
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-dim)]">
          {subtitle}
        </p>
      )}
    </div>
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
    <div className="m-4 rounded-xl border border-[color:rgba(194,65,58,0.22)] bg-[color:rgba(194,65,58,0.07)] p-4 text-sm text-[var(--color-danger)] shadow-sm sm:m-6 lg:m-10">
      <div className="font-medium">{message}</div>
      <div className="text-[var(--color-text-dim)] mt-1">{hint}</div>
    </div>
  );
}
