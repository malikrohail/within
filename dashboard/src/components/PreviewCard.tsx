import type { Preview, Risk } from "../preview";

const VALUE: Record<Risk, string> = { info: "text-muted", warn: "text-amber", danger: "text-bad" };

/** A plain-English transaction card from the Preview module. `compact` is the smaller feed variant. */
export function PreviewCard({ preview, compact = false }: { preview: Preview; compact?: boolean }) {
  return (
    <div className={`rounded-lg border border-line bg-ink/60 ${compact ? "p-3 text-xs" : "p-4 text-sm"}`}>
      <div className={`font-bold ${compact ? "" : "text-base"}`}>{preview.title}</div>
      {!compact && preview.summary !== preview.title && <div className="text-xs text-muted">{preview.summary}</div>}
      <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1">
        {preview.lines.map((l, i) => (
          // "#n …" labels are the inner transactions of a Batch.
          <div key={i} className={`contents ${/^#\d/.test(l.label) ? "[&>dt]:pl-4" : ""}`}>
            <dt className="whitespace-nowrap text-muted">{l.label}</dt>
            <dd className={`flex min-w-0 items-center gap-2 ${l.risk ? VALUE[l.risk] : ""}`}>
              <span className="truncate" title={l.full ?? l.value}>
                {l.value}
              </span>
              {l.risk === "danger" && (
                <span className="shrink-0 rounded px-1.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-bad/50">danger</span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
