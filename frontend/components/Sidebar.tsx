"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/customers", label: "Customers" },
  { href: "/orders", label: "Captured Orders" },
  { href: "/catalog", label: "Catalog" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 z-20 flex w-full shrink-0 flex-col border-b bg-[color:rgba(255,255,255,0.88)] shadow-[0_1px_0_rgba(16,35,33,0.04)] backdrop-blur-xl md:min-h-screen md:w-64 md:border-b-0 md:border-r">
      <div className="border-b px-4 py-4 sm:px-6 md:px-6 md:py-7">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-accent)] text-sm font-semibold text-white shadow-sm">
            Ai
          </div>
          <div>
            <div className="text-lg font-semibold leading-tight tracking-[-0.01em] text-[var(--color-text)]">
              Aisle
            </div>
            <div className="mt-0.5 text-xs font-medium text-[var(--color-text-dim)]">
              call assistant console
            </div>
          </div>
        </div>
      </div>

      <nav className="flex gap-1 overflow-x-auto px-3 py-3 md:block md:flex-1 md:space-y-1 md:px-3 md:py-5">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`whitespace-nowrap rounded-lg border px-3 py-2 text-sm font-medium transition md:block md:px-3 md:py-2.5 ${
                active
                  ? "border-[color:rgba(15,118,110,0.22)] bg-[color:rgba(15,118,110,0.09)] text-[var(--color-accent)] shadow-[inset_0_0_0_1px_rgba(15,118,110,0.04)]"
                  : "border-transparent text-[var(--color-text-dim)] hover:border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text)]"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="hidden border-t px-6 py-5 text-xs font-medium text-[var(--color-text-dim)] md:block">
        demo build
      </div>
    </aside>
  );
}
