import {
  Card,
  PageContent,
  PageHeader,
  SectionTitle,
  Skeleton,
} from "@/components/ui";

export default function OverviewLoading() {
  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Monitor Foodie's AI voice ordering workflow across shoppers, calls, captured orders, and catalog readiness."
      />
      <PageContent className="space-y-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-5">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="mt-4 h-9 w-20" />
              <Skeleton className="mt-5 h-3 w-32" />
            </Card>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
          <section>
            <SectionTitle
              title="Recent captured orders"
              subtitle="Latest order records created by completed assistant calls."
            />
            <Card className="overflow-hidden">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className={`flex items-center gap-4 px-4 py-4 sm:px-5 ${
                    i > 0 ? "border-t" : ""
                  }`}
                >
                  <Skeleton className="h-9 w-9 rounded-xl" />
                  <Skeleton className="h-4 flex-1" />
                  <Skeleton className="h-4 w-16" />
                </div>
              ))}
            </Card>
          </section>

          <section>
            <SectionTitle
              title="Operations readiness"
              subtitle="A quick read on outreach and catalog quality."
            />
            <Card className="overflow-hidden">
              <div className="space-y-4 p-5">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="h-11 w-14 rounded-2xl" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-3 w-32" />
                      <Skeleton className="h-3 w-44" />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </section>
        </div>
      </PageContent>
    </div>
  );
}
