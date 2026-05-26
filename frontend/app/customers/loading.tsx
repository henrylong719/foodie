import {
  Card,
  PageContent,
  PageHeader,
  SectionTitle,
  Skeleton,
} from "@/components/ui";

export default function CustomersLoading() {
  return (
    <div>
      <PageHeader title="Customers" />
      <PageContent>
        <SectionTitle
          title="Customer outreach"
          subtitle="Call actions are hidden for customers flagged do-not-call."
        />
        <Card className="overflow-hidden">
          <div className="grid grid-cols-[minmax(240px,1fr)_180px_150px_110px] items-center gap-4 border-b bg-[var(--color-surface-2)] px-5 py-3">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-14" />
            <Skeleton className="h-3 w-14" />
            <Skeleton className="ml-auto h-3 w-12" />
          </div>
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="grid grid-cols-[minmax(240px,1fr)_180px_150px_110px] items-center gap-4 border-t px-5 py-4 first:border-t-0"
            >
              <div className="flex items-center gap-3">
                <Skeleton className="h-9 w-9 rounded-xl" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-20" />
                </div>
              </div>
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-6 w-20 rounded-full" />
              <Skeleton className="ml-auto h-9 w-16 rounded-full" />
            </div>
          ))}
        </Card>
      </PageContent>
    </div>
  );
}
