import {
  Card,
  PageContent,
  PageHeader,
  SectionTitle,
  Skeleton,
} from "@/components/ui";

export default function OrdersLoading() {
  return (
    <div>
      <PageHeader
        title="Captured Orders"
        subtitle="Review voice-captured grocery orders, confirm AI brand choices, and move clean orders toward fulfillment."
      />
      <PageContent className="space-y-6">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border bg-[color:rgba(255,255,255,0.74)] p-4"
            >
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-8 w-16" />
              <Skeleton className="mt-4 h-3 w-32" />
            </div>
          ))}
        </div>

        <SectionTitle
          title="Review queue"
          subtitle="Recommended brand choices are highlighted because they carry the most operational risk."
        />
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="overflow-hidden">
              <div className="grid gap-4 border-b bg-[var(--color-surface-2)] px-4 py-4 sm:px-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                <div className="flex min-w-0 gap-3 sm:gap-4">
                  <Skeleton className="h-11 w-11 rounded-xl" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-44" />
                    <Skeleton className="h-3 w-60" />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 lg:justify-end">
                  <Skeleton className="h-6 w-20 rounded-full" />
                  <Skeleton className="h-6 w-20 rounded-full" />
                  <Skeleton className="h-9 w-24 rounded-full" />
                </div>
              </div>
              <div className="px-4 py-4 sm:px-5">
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  {Array.from({ length: 4 }).map((_, j) => (
                    <Skeleton key={j} className="h-[74px] rounded-xl" />
                  ))}
                </div>
              </div>
            </Card>
          ))}
        </div>
      </PageContent>
    </div>
  );
}
