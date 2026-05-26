"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/customers", label: "Customers" },
  { href: "/calls", label: "Call History" },
  { href: "/orders", label: "Captured Orders" },
  { href: "/catalog", label: "Catalog" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 z-20 flex w-full shrink-0 flex-col border-b bg-[color:rgba(255,255,255,0.92)] shadow-[0_1px_0_rgba(32,35,31,0.05)] backdrop-blur-xl md:h-screen md:w-[17rem] md:self-start md:overflow-y-auto md:border-b-0 md:border-r">
      <div className="border-b px-4 py-4 sm:px-6 md:px-6 md:py-7">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--color-accent)] text-sm font-bold text-white shadow-[0_10px_24px_rgba(33,122,74,0.22)]">
            Fd
          </div>
          <div>
            <div className="text-lg font-semibold leading-tight text-[var(--color-text)]">
              Foodie
            </div>
            <div className="mt-0.5 text-xs font-medium text-[var(--color-text-dim)]">
              AI ordering console
            </div>
          </div>
        </div>
      </div>

      <nav className="flex gap-1 overflow-x-auto px-3 py-3 md:block md:flex-1 md:space-y-1 md:px-3 md:py-5">
        {NAV.map((item) => {
          const active =
            item.href === "/" || item.href === "/calls"
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group relative flex items-center gap-3 whitespace-nowrap rounded-xl border px-3 py-2 text-sm font-medium transition md:px-3.5 md:py-2.5 ${
                active
                  ? "border-[color:rgba(33,122,74,0.18)] bg-[color:rgba(33,122,74,0.08)] text-[var(--color-accent)] shadow-[inset_0_0_0_1px_rgba(33,122,74,0.04)]"
                  : "border-transparent text-[var(--color-text-dim)] hover:border-[var(--color-border)] hover:bg-[color:rgba(241,245,238,0.78)] hover:text-[var(--color-text)]"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full transition ${
                  active
                    ? "bg-[var(--color-accent)]"
                    : "bg-[var(--color-border-strong)] opacity-55 group-hover:bg-[var(--color-text-dim)] group-hover:opacity-80"
                }`}
              />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="hidden border-t px-6 py-5 md:block">
        <div className="rounded-2xl border bg-[var(--color-surface-2)] p-4">
          <div className="text-xs font-semibold text-[var(--color-text)]">
            Staff dashboard
          </div>
          <div className="mt-1 text-xs leading-5 text-[var(--color-text-dim)]">
            Voice ordering, customer outreach, and captured grocery orders.
          </div>
        </div>
      </div>
    </aside>
  );
}
