import {
  Card,
  PageContent,
  PageHeader,
  SectionTitle,
  Skeleton,
} from "@/components/ui";

export default function CallsLoading() {
  return (
    <div>
      <PageHeader title="Call History" />
      <PageContent>
        <SectionTitle
          title="Audit trail"
          subtitle="Review placed, blocked, and failed call attempts with their compliance decision."
        />
        <Card className="overflow-hidden">
          <div className="grid grid-cols-[minmax(220px,1fr)_160px_120px_120px_minmax(220px,1.1fr)_120px] items-center gap-4 border-b bg-[var(--color-surface-2)] px-5 py-3">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-14" />
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-24" />
            <Skeleton className="ml-auto h-3 w-12" />
          </div>
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="grid grid-cols-[minmax(220px,1fr)_160px_120px_120px_minmax(220px,1.1fr)_120px] items-center gap-4 border-t px-5 py-4 first:border-t-0"
            >
              <div className="flex items-center gap-3">
                <Skeleton className="h-9 w-9 rounded-xl" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-36" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-6 w-16 rounded-full" />
              <Skeleton className="h-3 w-16" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-44" />
              </div>
              <Skeleton className="ml-auto h-9 w-24 rounded-full" />
            </div>
          ))}
        </Card>
      </PageContent>
    </div>
  );
}
