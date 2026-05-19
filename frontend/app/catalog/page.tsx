"use client";

import { useEffect, useState } from "react";
import { listProducts, listCategories } from "@/lib/api";
import type { Product } from "@/lib/types";
import { PageHeader, ErrorNote, StockDot } from "@/components/ui";

export default function CatalogPage() {
  const [categories, setCategories] = useState<string[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listCategories()
      .then((r) => setCategories(r.categories))
      .catch((e) => setError((e as Error).message));
  }, []);

  useEffect(() => {
    setLoading(true);
    listProducts(active ?? undefined)
      .then((r) => setProducts(r.products))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [active]);

  if (error) {
    return (
      <div>
        <PageHeader title="Catalog" />
        <ErrorNote message={error} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Catalog"
        subtitle="Products the assistant can resolve and recommend"
      />

      <div className="flex flex-wrap gap-2 border-b bg-[color:rgba(255,255,255,0.5)] px-4 py-4 backdrop-blur sm:px-6 lg:px-10">
        <FilterChip
          label="All"
          active={active === null}
          onClick={() => setActive(null)}
        />
        {categories.map((c) => (
          <FilterChip
            key={c}
            label={c}
            active={active === c}
            onClick={() => setActive(c)}
          />
        ))}
      </div>

      <div className="px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        {loading ? (
          <p className="rounded-2xl border border-dashed bg-[color:rgba(255,255,255,0.72)] px-5 py-8 text-sm text-[var(--color-text-dim)] shadow-sm">
            Loading…
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {products.map((p) => (
              <div
                key={p._id}
                className="row-in rounded-2xl border bg-[color:rgba(255,255,255,0.86)] p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-[color:rgba(15,118,110,0.22)] hover:shadow-md"
              >
                <div className="flex items-start gap-3">
                  <StockDot inStock={p.in_stock} />
                  <span className="min-w-0 flex-1 text-sm font-medium leading-snug text-[var(--color-text)]">
                    {p.name}
                  </span>
                </div>
                <div className="mt-4 flex items-center gap-2 text-xs text-[var(--color-text-dim)]">
                  <span className="truncate">{p.brand}</span>
                  <span className="text-[var(--color-border-strong)]">/</span>
                  <span className="truncate">{p.subcategory}</span>
                  <span className="flex-1" />
                  <span
                    className="shrink-0 font-medium text-[var(--color-accent)]"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    ${p.price.toFixed(2)}
                  </span>
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-[var(--color-text-dim)]">
                    popularity
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--color-surface-3)]">
                    <div
                      className="h-full rounded-full bg-[var(--color-accent)]"
                      style={{ width: `${p.popularity_score}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3.5 py-2 text-xs font-semibold transition-colors ${
        active
          ? "border-[color:rgba(15,118,110,0.24)] bg-[color:rgba(15,118,110,0.1)] text-[var(--color-accent)]"
          : "bg-[color:rgba(255,255,255,0.7)] text-[var(--color-text-dim)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
      }`}
    >
      {label}
    </button>
  );
}
