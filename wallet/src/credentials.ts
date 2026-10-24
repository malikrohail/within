// On-ledger merchant allowlist: XRPL Credential objects issued by the operator.
import type { CredentialCreate, CredentialDelete, PermissionedDomainSet, TransactionMetadata, Wallet } from "xrpl";
import type { XrplConnection } from "./xrpl.js";

export const LSF_ACCEPTED = 0x00010000;
export const RIPPLE_EPOCH_OFFSET = 946684800;
export const CACHE_MS = 30_000;

export const credentialTypeHex = (type: string) => Buffer.from(type, "utf8").toString("hex").toUpperCase();

export type CredentialEntry = {
  Subject: string;
  Issuer: string;
  CredentialType: string;
  Flags: number;
  Expiration?: number;
  PreviousTxnID: string;
};
/** Engine result of the transaction. `txHash` is null when it never validated (tem*, or LastLedgerSequence passed). */
export type Submitted = { engineResult: string; txHash: string | null };
export type MerchantRow = { address: string; accepted: boolean; txHash: string };
export type DomainEntry = {
  index: string;
  Owner: string;
  AcceptedCredentials: { Credential: { Issuer: string; CredentialType: string } }[];
  PreviousTxnID: string;
};
/** The Permissioned Domain whose membership is the vet credential. */
export type DomainRow = { domainId: string; owner: string; acceptedCredentials: { issuer: string; credentialType: string }[]; txHash: string };

/** The ledger calls the allowlist needs; fakeable in tests. */
export interface CredentialRpc {
  /** The validated Credential object, or null when it does not exist. Throws on any other RPC error. */
  credential(subject: string, issuer: string, typeHex: string): Promise<CredentialEntry | null>;
  /** One page of the account's Credential objects (issued or received). */
  credentialPage(account: string, marker?: unknown): Promise<{ entries: CredentialEntry[]; marker?: unknown }>;
  /** Autofill, sign, submit, wait for validation. Engine failures resolve with their code; RPC failures throw. */
  submit(tx: CredentialCreate | CredentialDelete | PermissionedDomainSet, wallet: Wallet): Promise<Submitted>;
  /** PermissionedDomain objects owned by `owner`. */
  domains(owner: string): Promise<DomainEntry[]>;
}

export function clientCredentialRpc(xrpl: Pick<XrplConnection, "read" | "get">): CredentialRpc {
  return {
    async credential(subject, issuer, typeHex) {
      try {
        // rippled wants `credential_type`; the xrpl.js 5.3.0 d.ts says `credentialType`, which rippled rejects as malformedRequest.
        const credential = { subject, issuer, credential_type: typeHex } as unknown as { subject: string; issuer: string; credentialType: string };
        const r = await xrpl.read((c) => c.request({ command: "ledger_entry", credential, ledger_index: "validated" }));
        return r.result.node as unknown as CredentialEntry;
      } catch (e) {
        if ((e as { data?: { error?: string } }).data?.error === "entryNotFound") return null;
        throw e;
      }
    },
    async credentialPage(account, marker) {
      const r = await xrpl.read((c) => c.request({ command: "account_objects", account, type: "credential", ledger_index: "validated", marker }));
      return { entries: r.result.account_objects as unknown as CredentialEntry[], marker: r.result.marker };
    },
    async domains(owner) {
      const r = await xrpl.read((c) => c.request({ command: "account_objects", account: owner, type: "permissioned_domain", ledger_index: "validated" }));
      return r.result.account_objects as unknown as DomainEntry[];
    },
    async submit(tx, wallet) {
      try {
        // No retry: a resubmit after an unclear failure could land the transaction twice.
        const r = await (await xrpl.get()).submitAndWait(tx, { autofill: true, wallet });
        return { engineResult: (r.result.meta as TransactionMetadata).TransactionResult, txHash: r.result.hash };
      } catch (e) {
        // submitAndWait throws on tem* and on a passed LastLedgerSequence, naming the engine code.
        const code = /\b(te[mflr][A-Z_]+)\b/.exec((e as Error).message)?.[1];
        if (code) return { engineResult: code, txHash: null };
        throw e;
      }
    },
  };
}

/** Accepted and not expired at `nowMs`. */
export function isValidCredential(entry: CredentialEntry | null, nowMs: number): boolean {
  if (!entry || (entry.Flags & LSF_ACCEPTED) === 0) return false;
  return entry.Expiration === undefined || entry.Expiration > Math.floor(nowMs / 1000) - RIPPLE_EPOCH_OFFSET;
}

/** Rule 3's ledger lookup (cached per issuer, type, and merchant) and the issuer's vet/revoke transactions. */
export class Credentials {
  private cache = new Map<string, { ok: boolean; until: number }>();

  constructor(
    private readonly rpc: CredentialRpc,
    private readonly issuer: Wallet,
  ) {}

  /** Throws on an RPC error, which is not cached; the caller fails closed. */
  async check(subject: string, issuer: string, type: string): Promise<boolean> {
    const key = `${issuer}|${type}|${subject}`;
    const hit = this.cache.get(key);
    if (hit && hit.until > Date.now()) return hit.ok;
    const ok = isValidCredential(await this.rpc.credential(subject, issuer, credentialTypeHex(type)), Date.now());
    this.cache.set(key, { ok, until: Date.now() + CACHE_MS });
    return ok;
  }

  forget(subject: string): void {
    for (const key of this.cache.keys()) if (key.endsWith(`|${subject}`)) this.cache.delete(key);
  }

  async create(subject: string, type: string): Promise<Submitted> {
    const tx: CredentialCreate = {
      TransactionType: "CredentialCreate", Account: this.issuer.classicAddress, Subject: subject, CredentialType: credentialTypeHex(type),
    };
    try {
      return await this.rpc.submit(tx, this.issuer);
    } finally {
      this.forget(subject);
    }
  }

  async remove(subject: string, type: string): Promise<Submitted> {
    const tx: CredentialDelete = {
      TransactionType: "CredentialDelete", Account: this.issuer.classicAddress, Subject: subject, CredentialType: credentialTypeHex(type),
    };
    try {
      return await this.rpc.submit(tx, this.issuer);
    } finally {
      this.forget(subject);
    }
  }

  /** The issuer's domain that accepts exactly this credential, or null. */
  async domain(type: string): Promise<DomainRow | null> {
    const issuer = this.issuer.classicAddress;
    const typeHex = credentialTypeHex(type);
    const d = (await this.rpc.domains(issuer)).find(
      (e) => e.AcceptedCredentials.length === 1 && e.AcceptedCredentials[0].Credential.Issuer === issuer && e.AcceptedCredentials[0].Credential.CredentialType === typeHex,
    );
    if (!d) return null;
    const acceptedCredentials = d.AcceptedCredentials.map(({ Credential: c }) => ({ issuer: c.Issuer, credentialType: Buffer.from(c.CredentialType, "hex").toString("utf8") }));
    return { domainId: d.index, owner: d.Owner, acceptedCredentials, txHash: d.PreviousTxnID };
  }

  /** Creates the domain, or updates the issuer's first domain so membership = this credential. */
  async setDomain(type: string): Promise<Submitted> {
    const issuer = this.issuer.classicAddress;
    const existing = (await this.rpc.domains(issuer))[0];
    const tx: PermissionedDomainSet = {
      TransactionType: "PermissionedDomainSet",
      Account: issuer,
      ...(existing ? { DomainID: existing.index } : {}),
      AcceptedCredentials: [{ Credential: { Issuer: issuer, CredentialType: credentialTypeHex(type) } }],
    };
    return this.rpc.submit(tx, this.issuer);
  }

  /** Credentials `issuer` has issued with this type, accepted or not. */
  async list(issuer: string, type: string): Promise<MerchantRow[]> {
    const typeHex = credentialTypeHex(type);
    const rows: MerchantRow[] = [];
    let marker: unknown;
    do {
      const page = await this.rpc.credentialPage(issuer, marker);
      for (const e of page.entries) {
        if (e.Issuer !== issuer || e.CredentialType !== typeHex) continue;
        rows.push({ address: e.Subject, accepted: (e.Flags & LSF_ACCEPTED) !== 0, txHash: e.PreviousTxnID });
      }
      marker = page.marker;
    } while (marker != null);
    return rows;
  }
}
