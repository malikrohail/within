import type { RequestStatus } from "../api";

const STYLES: Record<RequestStatus, string> = {
  auto: "bg-ok/15 text-ok ring-ok/40",
  approved: "bg-ok/15 text-ok ring-ok/40",
  held: "bg-amber/15 text-amber ring-amber/40",
  refused: "bg-bad/15 text-bad ring-bad/40",
  expired: "bg-bad/15 text-bad ring-bad/40",
};

export function Pill({ status }: { status: RequestStatus }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1 ${STYLES[status] ?? "bg-white/10 text-muted ring-white/20"}`}
    >
      {status}
    </span>
  );
}
