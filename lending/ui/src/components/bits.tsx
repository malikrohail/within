import { useState, type ReactNode } from "react";
import { accountUrl, short, txUrl } from "../format";
import type { LoanRequest } from "../types";

const svg = (children: ReactNode, sw = 1.8) => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

export const Icon = {
  clock: () =>
    svg(
      <>
        <circle cx="8" cy="8" r="6.2" />
        <path d="M8 4.5V8l2.4 1.6" />
      </>,
    ),
  check: () => svg(<path d="M3 8.5l3 3 7-7" />, 2),
  x: () => svg(<path d="M4 4l8 8M12 4l-8 8" />, 2),
  warn: () =>
    svg(
      <>
        <path d="M8 2.2L14.5 13.5h-13z" />
        <path d="M8 6.5v3.2M8 11.6v.1" />
      </>,
    ),
  ext: () => svg(<path d="M6 3H3v10h10v-3M9 3h4v4M13 3L7.5 8.5" />, 1.6),
  copy: () =>
    svg(
      <>
        <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" />
        <path d="M10.5 5.5V3.5a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2" />
      </>,
      1.5,
    ),
  chevron: () => svg(<path d="M4 6l4 4 4-4" />, 1.8),
  moon: () => svg(<path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z" />, 1.5),
  sun: () =>
    svg(
      <>
        <circle cx="8" cy="8" r="3" />
        <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" />
      </>,
      1.5,
    ),
};

export function Dot({ tone }: { tone?: "ok" | "warn" | "bad" | "dim" }) {
  return <span className={`dot ${tone && tone !== "ok" ? tone : ""}`} />;
}

function CopyBtn({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      title={done ? "Copied" : `Copy ${label}`}
      aria-label={`Copy ${label}`}
      onClick={(e) => {
        e.stopPropagation();
        try {
          void navigator.clipboard?.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        } catch {
          /* clipboard blocked */
        }
      }}
    >
      {done ? Icon.check() : Icon.copy()}
    </button>
  );
}

/** Truncated tx hash in mono: explorer link + copy button. */
export function Hash({ hash }: { hash: string | null | undefined }) {
  if (!hash) return null;
  return (
    <span className="hash">
      <a href={txUrl(hash)} target="_blank" rel="noreferrer" title={hash}>
        {short(hash)}
        {Icon.ext()}
      </a>
      <CopyBtn text={hash} label="transaction hash" />
    </span>
  );
}

/** Truncated address in mono: account link + copy button. */
export function Addr({ addr, plain }: { addr: string | null | undefined; plain?: boolean }) {
  if (!addr) return <span className="muted">-</span>;
  if (plain) return <span className="mono" title={addr}>{short(addr)}</span>;
  return (
    <span className="hash">
      <a href={accountUrl(addr)} target="_blank" rel="noreferrer" title={addr} style={{ color: "inherit" }}>
        {short(addr)}
      </a>
      <CopyBtn text={addr} label="address" />
    </span>
  );
}

/** "View on explorer ↗" link. */
export function Explorer({ hash, children }: { hash: string; children?: ReactNode }) {
  return (
    <a className="ext" href={txUrl(hash)} target="_blank" rel="noreferrer" title={hash}>
      {children ?? "View on explorer"}
      {Icon.ext()}
    </a>
  );
}

/** The latest agent note on a request, in italics, prefixed by the agent name. Display only. */
export function LatestNote({ r }: { r: LoanRequest }) {
  const n = r.notes?.[r.notes.length - 1];
  if (!n) return null;
  return (
    <p className="note">
      <em>
        {n.from}: {n.text}
      </em>
    </p>
  );
}
