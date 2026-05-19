"use client";

import { useEffect, useState } from "react";
import { listProducts, listCategories } from "@/lib/api";
import type { Product } from "@/lib/types";
import {
  Card,
  EmptyState,
  ErrorNote,
  PageContent,
  PageHeader,
  SectionTitle,
  StatusBadge,
  StockDot,
} from "@/components/ui";

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

      <div className="border-b bg-[color:rgba(255,255,255,0.56)] backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl gap-2 overflow-x-auto px-4 py-4 sm:px-6 md:flex-wrap md:overflow-visible lg:px-8">
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
      </div>

      <PageContent>
        <SectionTitle
          title="Product resolver"
          subtitle="Stock, pricing, category, and popularity signals used by the assistant."
        />
        {loading ? (
          <EmptyState title="Loading catalog">
            Fetching products and category metadata.
          </EmptyState>
        ) : products.length === 0 ? (
          <EmptyState
            title="No products found"
            action={
              active ? (
                <button
                  onClick={() => setActive(null)}
                  className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                >
                  Show all products
                </button>
              ) : null
            }
          >
            Try another category or check the catalog source.
          </EmptyState>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {products.map((p) => (
              <Card
                key={p._id}
                className="row-in p-5 transition hover:-translate-y-0.5 hover:border-[color:rgba(33,122,74,0.22)] hover:shadow-[0_1px_2px_rgba(32,35,31,0.05),0_18px_40px_rgba(32,35,31,0.075)]"
              >
                <div className="flex items-start gap-3">
                  <StockDot inStock={p.in_stock} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold leading-snug text-[var(--color-text)]">
                      {p.name}
                    </div>
                    <div className="mt-1 truncate text-xs text-[var(--color-text-dim)]">
                      {p.brand}
                    </div>
                  </div>
                  <span
                    className="shrink-0 text-sm font-semibold text-[var(--color-accent)]"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    ${p.price.toFixed(2)}
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <span className="rounded-full border bg-[var(--color-surface-2)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--color-text-dim)]">
                    {p.category}
                  </span>
                  <span className="rounded-full border bg-white px-2.5 py-1 text-[11px] font-medium text-[var(--color-text-dim)]">
                    {p.subcategory}
                  </span>
                  <StatusBadge
                    status={p.in_stock ? "in_stock" : "out_of_stock"}
                  />
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-dim)]">
                    popularity
                  </span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--color-surface-3)]">
                    <div
                      className="h-full rounded-full bg-[var(--color-accent-dim)]"
                      style={{ width: `${p.popularity_score}%` }}
                    />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </PageContent>
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
      className={`shrink-0 rounded-full border px-3.5 py-2 text-xs font-semibold transition-colors ${
        active
          ? "border-[color:rgba(33,122,74,0.32)] bg-[color:rgba(33,122,74,0.12)] text-[var(--color-accent)] shadow-[inset_0_0_0_1px_rgba(33,122,74,0.05)]"
          : "bg-[color:rgba(255,255,255,0.72)] text-[var(--color-text-dim)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
      }`}
    >
      {label}
    </button>
  );
}
