import Link from "next/link";
import { listCalls } from "@/lib/api";
import {
  Card,
  EmptyState,
  ErrorNote,
  PageContent,
  PageHeader,
  SectionTitle,
  StatusBadge,
} from "@/components/ui";

export const dynamic = "force-dynamic";

const callDateFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Australia/Sydney",
  timeZoneName: "short",
});

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return callDateFormatter.format(new Date(iso));
}

function formatComplianceReason(reason: string | null): string {
  if (!reason) return "allowed";
  return reason.replace(/_/g, " ");
}

export default async function CallsPage() {
  try {
    const { calls, count } = await listCalls();

    return (
      <div>
        <PageHeader
          title="Call History"
          subtitle={`${count} recent call records from Foodie's outbound ordering workflow.`}
        />

        <PageContent>
          <SectionTitle
            title="Audit trail"
            subtitle="Review placed, blocked, and failed call attempts with their compliance decision."
          />
          {calls.length === 0 ? (
            <EmptyState
              title="No calls recorded yet"
              action={
                <Link
                  href="/customers"
                  className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                >
                  View customers
                </Link>
              }
            >
              Once an outbound call is attempted, its status and compliance
              result will appear here.
            </EmptyState>
          ) : (
            <Card className="overflow-x-auto [scrollbar-gutter:stable]">
              <div className="min-w-[860px]">
                <div className="grid grid-cols-[minmax(220px,1fr)_160px_120px_120px_minmax(220px,1.1fr)_120px] items-center gap-4 border-b bg-[var(--color-surface-2)] px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-dim)]">
                  <span>Customer</span>
                  <span>Created</span>
                  <span>Status</span>
                  <span>Transcript</span>
                  <span>Compliance</span>
                  <span className="text-right">Action</span>
                </div>
                {calls.map((call) => (
                  <div
                    key={call._id}
                    className="grid grid-cols-[minmax(220px,1fr)_160px_120px_120px_minmax(220px,1.1fr)_120px] items-center gap-4 border-t px-5 py-4 text-sm transition first:border-t-0 hover:bg-[color:rgba(241,245,238,0.72)]"
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[color:rgba(33,122,74,0.09)] text-xs font-semibold text-[var(--color-accent)]">
                        {call.customer_name.slice(0, 2).toUpperCase() || "C"}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-[var(--color-text)]">
                          {call.customer_name || "Unknown customer"}
                        </span>
                        <span
                          className="mt-0.5 block truncate text-xs text-[var(--color-text-dim)]"
                          style={{ fontFamily: "var(--font-mono)" }}
                        >
                          {call.phone || "-"}
                        </span>
                      </span>
                    </span>
                    <span className="text-xs text-[var(--color-text-dim)]">
                      {formatDate(call.created_at)}
                    </span>
                    <span>
                      <StatusBadge
                        status={call.status}
                        className="whitespace-nowrap"
                      >
                        {call.status === "queued" ? "placed" : undefined}
                      </StatusBadge>
                      {call.dry_run && (
                        <span className="ml-2 text-xs font-medium text-[var(--color-text-dim)]">
                          dry run
                        </span>
                      )}
                    </span>
                    <span
                      className="text-xs text-[var(--color-text-dim)]"
                      style={{ fontFamily: "var(--font-mono)" }}
                    >
                      {call.transcript_count ?? 0} lines
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-[var(--color-text)]">
                        {formatComplianceReason(call.compliance.reason)}
                      </span>
                      <span className="mt-0.5 block truncate text-xs text-[var(--color-text-dim)]">
                        {call.compliance.message || "Compliance gate allowed the call."}
                      </span>
                    </span>
                    <span className="text-right">
                      {call.vapi_call_id ? (
                        <Link
                          href={`/calls/${call.vapi_call_id}`}
                          className="inline-flex h-9 items-center rounded-full border border-[color:rgba(33,122,74,0.24)] bg-[color:rgba(33,122,74,0.08)] px-4 text-xs font-semibold text-[var(--color-accent)] transition hover:-translate-y-px hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white"
                        >
                          {(call.transcript_count ?? 0) > 0
                            ? "Transcript"
                            : "Fetch transcript"}
                        </Link>
                      ) : (
                        <span className="text-xs font-medium text-[var(--color-text-dim)]">
                          No transcript
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </PageContent>
      </div>
    );
  } catch (e) {
    return (
      <div>
        <PageHeader title="Call History" />
        <ErrorNote message={(e as Error).message} />
      </div>
    );
  }
}
