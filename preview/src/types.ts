export type Risk = "info" | "warn" | "danger";

/** One row of a preview card. `full` is the untruncated value (shown on hover). */
export type Line = { label: string; value: string; risk?: Risk; full?: string };

export type Preview = { title: string; lines: Line[]; summary: string };

export type Ctx = {
  /** Known accounts: address → name ("treasury", "agent", "good merchant"). */
  names?: Record<string, string>;
  network?: string;
  /** Clock for relative times, ms since epoch (tests pin it). */
  now?: number;
};

export type Tx = Record<string, unknown>;

/**
 * One field of a descriptor. `path` is a dot path into tx_json ("Amount.value"). `format` names a
 * formatter (formats.ts); a missing field is skipped unless `required` is set, which shows "missing".
 */
export type FieldSpec = { path: string; label: string; format?: string; risk?: Risk; required?: boolean };

/** `when` grammar: "Path", "!Path", "Path & 0x10000", "Path == 3", "Path != \"x\"", "len(Path) == 0". */
export type RiskRule = { when: string; level: Risk; text: string };

/** One metadata file per TransactionType (preview/format/<Type>.json). */
export type Descriptor = {
  type: string;
  /** Intent title with placeholders: "{Path}" or "{Path|format}". */
  title: string;
  /** One sentence; defaults to the title. Same placeholders. */
  summary?: string;
  /** The first variant whose `when` holds replaces title/summary (grant vs revoke, default vs impair). */
  variants?: { when: string; title: string; summary?: string }[];
  fields: FieldSpec[];
  risk?: RiskRule[];
};

/** What a formatter returns: a value, a value with extras, or whole lines (memos, inner transactions). */
export type Formatted = string | { value: string; full?: string; risk?: Risk } | Line[];

export type Formatter = (value: unknown, tx: Tx, ctx: Ctx, describe: (tx: Tx, ctx?: Ctx) => Preview) => Formatted;
