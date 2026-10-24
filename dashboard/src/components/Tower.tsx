import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type Simulation, type SimulationNodeDatum } from "d3-force";
import { useEffect, useMemo, useRef, useState } from "react";
import { getAccounts, type WalletRequest, type WalletStatus } from "../api";
import { shortAccount, shortHash } from "../format";
import {
  cacheKey,
  EXPLORER,
  flowsFromRequests,
  isIncident,
  latestRun,
  flowsFromTx,
  KIND_COLOR,
  KIND_LABEL,
  type Accounts,
  type Flow,
  type GraphNode,
  type Kind,
  type Network,
  type Role,
} from "../tower/flows";
import { LedgerStream } from "../tower/stream";

const W = 900;
const H = 520;
const PULSE_MS = 3000;

const ROLE_COLOR: Record<Role, string> = {
  treasury: "#e8a33d",
  agent: "#2bb3a3",
  merchant: "#e6edf3",
  broker: "#4a8fe7",
  supplier: "#9b87f5",
  borrower: "#7cc4fa",
  customer: "#8b98a5",
  vault: "#4a8fe7",
  lending: "#8b98a5",
  unknown: "#5b6672",
};

type SimNode = GraphNode & SimulationNodeDatum;
type Edge = { key: string; from: string; to: string; kind: Kind; network: Network; count: number; drops: number; lastHash: string | null; lastTs: number };

const asRole = (r: string): Role => (r in ROLE_COLOR ? (r as Role) : "unknown");

export function Tower({ requests, status }: { requests: WalletRequest[]; status: WalletStatus | null }) {
  const [accounts, setAccounts] = useState<Accounts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [links, setLinks] = useState<Record<Network, string>>({ testnet: "…", devnet: "…" });
  const ledgerFlows = useRef(new Map<string, Flow>());
  const pulses = useRef(new Map<string, number>());
  const [version, setVersion] = useState(0);
  const bump = () => setVersion((v) => v + 1);
  // "latest": each network's last run, incidents hidden (the stage view). "all": everything, incidents included.
  const [scope, setScope] = useState<"latest" | "all">("latest");
  const [cached, setCached] = useState<Record<Network, number>>({ testnet: 0, devnet: 0 });

  useEffect(() => {
    getAccounts().then(setAccounts, (e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  // One ledger stream per network, over the known accounts.
  useEffect(() => {
    if (!accounts) return;
    const roles = new Map<string, Role>();
    for (const net of ["testnet", "devnet"] as const) for (const a of accounts[net]) roles.set(a.address, asRole(a.role));
    const configuredVault = accounts.devnetObjects.vaultId;
    const vaultNode = (id: string | undefined) => `vault:${(id ?? configuredVault ?? "lending").slice(0, 8)}`;
    const nets = (["testnet", "devnet"] as const).filter((net) => accounts[net].length > 0);
    // Paint cached ledger flows first (validated txs never change). The key includes the exact account set.
    const keys = Object.fromEntries(nets.map((net) => [net, cacheKey(net, accounts[net].map((a) => a.address))])) as Record<Network, string>;
    for (const net of nets) {
      try {
        const saved = JSON.parse(localStorage.getItem(keys[net]) ?? "[]") as Flow[];
        for (const f of saved) ledgerFlows.current.set(f.id, f);
        setCached((c) => ({ ...c, [net]: saved.length }));
      } catch {
        // storage unavailable: start empty
      }
    }
    bump();
    const saveTimers: Partial<Record<Network, ReturnType<typeof setTimeout>>> = {};
    const save = (net: Network) => {
      clearTimeout(saveTimers[net]);
      saveTimers[net] = setTimeout(() => {
        try {
          const mine = [...ledgerFlows.current.values()].filter((f) => f.network === net).sort((a, b) => b.ts - a.ts).slice(0, 300);
          localStorage.setItem(keys[net], JSON.stringify(mine));
        } catch {
          // storage full or blocked: the cache is a convenience only
        }
      }, 1000);
    };
    const streams = nets
      .map(
        (net) =>
          new LedgerStream(
            net,
            accounts[net].map((a) => a.address),
            ({ tx, hash, date }, live) => {
              const fresh = flowsFromTx(tx, hash, date, { network: net, roleOf: (a) => roles.get(a), vaultNode }).filter((f) => !ledgerFlows.current.has(f.id));
              for (const f of fresh) {
                ledgerFlows.current.set(f.id, f);
                if (live) pulses.current.set(`${f.from}>${f.to}>${f.kind}`, Date.now());
              }
              if (fresh.length) {
                bump();
                save(net);
              }
            },
            (state) => setLinks((s) => ({ ...s, [net]: state })),
          ),
      );
    streams.forEach((s) => s.start());
    return () => {
      streams.forEach((s) => s.stop());
      Object.values(saveTimers).forEach(clearTimeout);
    };
  }, [accounts]);

  // Refusals come from the wallet (they never reach the ledger); pulse the ones that appear while open.
  const refusals = useMemo(() => flowsFromRequests(requests, status?.hotAccount ?? null, status?.deviceAccount ?? null), [requests, status]);
  const seenRefusals = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (seenRefusals.current === null) {
      seenRefusals.current = new Set(refusals.map((f) => f.id));
      return;
    }
    for (const f of refusals) {
      if (!seenRefusals.current.has(f.id)) {
        seenRefusals.current.add(f.id);
        pulses.current.set(`${f.from}>${f.to}>refused`, Date.now());
      }
    }
  }, [refusals]);

  const flows = useMemo(() => {
    const all = [...ledgerFlows.current.values(), ...refusals].sort((a, b) => b.ts - a.ts);
    return scope === "all" ? all : latestRun(all.filter((f) => !isIncident(f)));
  }, [version, refusals, scope]); // eslint-disable-line react-hooks/exhaustive-deps

  const { nodes, edges } = useMemo(() => {
    const nodes = new Map<string, GraphNode>();
    for (const net of ["testnet", "devnet"] as const) {
      for (const a of accounts?.[net] ?? []) nodes.set(a.address, { id: a.address, name: a.name, role: asRole(a.role), network: net });
    }
    // The current lending vault stays on the graph even when its last flow is outside the window.
    const vaultId = accounts?.devnetObjects.vaultId;
    if (vaultId) nodes.set(`vault:${vaultId.slice(0, 8)}`, { id: `vault:${vaultId.slice(0, 8)}`, name: "lending vault", role: "vault", network: "devnet" });
    const edges = new Map<string, Edge>();
    for (const f of flows) {
      for (const id of [f.from, f.to]) {
        if (!nodes.has(id)) {
          const vault = id.startsWith("vault:");
          const ours = vault && accounts?.devnetObjects.vaultId?.startsWith(id.slice(6));
          nodes.set(id, { id, name: ours ? "lending vault" : vault ? `vault ${id.slice(6)}…` : shortAccount(id), role: vault ? "vault" : "unknown", network: f.network });
        }
      }
      const key = `${f.from}>${f.to}>${f.kind}`;
      const e = edges.get(key) ?? { key, from: f.from, to: f.to, kind: f.kind, network: f.network, count: 0, drops: 0, lastHash: null, lastTs: 0 };
      e.count++;
      e.drops += f.drops;
      if (f.ts >= e.lastTs) {
        e.lastTs = f.ts;
        e.lastHash = f.hash ?? e.lastHash;
      }
      edges.set(key, e);
    }
    return { nodes: [...nodes.values()], edges: [...edges.values()] };
  }, [flows, accounts]);

  // d3-force layout. Positions persist across data updates; testnet clusters left, devnet right.
  const sim = useRef<Simulation<SimNode, undefined> | null>(null);
  const positions = useRef(new Map<string, SimNode>());
  const [, setTick] = useState(0);
  useEffect(() => {
    const simNodes: SimNode[] = nodes.map((n) => {
      const prev = positions.current.get(n.id);
      const node: SimNode = prev ? Object.assign(prev, n) : { ...n, x: n.network === "testnet" ? W * 0.3 : W * 0.7, y: H / 2 + (Math.random() - 0.5) * 80 };
      positions.current.set(n.id, node);
      return node;
    });
    const linkData = edges.filter((e) => positions.current.has(e.from) && positions.current.has(e.to)).map((e) => ({ source: e.from, target: e.to }));
    sim.current?.stop();
    let frame = 0;
    sim.current = forceSimulation<SimNode>(simNodes)
      .force("link", forceLink<SimNode, { source: string; target: string }>(linkData).id((d) => d.id).distance(120).strength(0.4))
      .force("charge", forceManyBody().strength(-380))
      .force("x", forceX<SimNode>((d) => (d.network === "testnet" ? W * 0.3 : W * 0.72)).strength(0.12))
      .force("y", forceY<SimNode>(H / 2).strength(0.08))
      .force("center", forceCenter(W / 2, H / 2).strength(0.02))
      .force("collide", forceCollide(34))
      .alpha(0.6)
      .on("tick", () => {
        for (const n of simNodes) {
          n.x = Math.max(40, Math.min(W - 40, n.x ?? 0));
          n.y = Math.max(30, Math.min(H - 30, n.y ?? 0));
        }
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => setTick((t) => t + 1));
      });
    return () => {
      sim.current?.stop();
      cancelAnimationFrame(frame);
    };
  }, [nodes, edges]);

  // Re-render while a pulse is running so it fades out.
  useEffect(() => {
    const t = setInterval(() => {
      const now = Date.now();
      for (const [k, at] of pulses.current) if (now - at > PULSE_MS) pulses.current.delete(k);
      if (pulses.current.size) setTick((x) => x + 1);
    }, 200);
    return () => clearInterval(t);
  }, []);

  const pos = (id: string) => positions.current.get(id);
  const width = (drops: number) => 1.5 + Math.min(9, 2.2 * Math.log10(1 + drops / 1e6));
  const now = Date.now();

  return (
    <section className="panel">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="panel-title !mb-0">Treasury: live money flow</h2>
        <div className="font-mono text-xs text-muted">
          {(["testnet", "devnet"] as const).map((net, i) => (
            <span key={net}>
              {i > 0 && " · "}
              {net} {!links[net].startsWith("live") && cached[net] > 0 ? `history (${cached[net]} cached) · ${links[net]}` : links[net]}
            </span>
          ))}
        </div>
      </div>
      {error && <p className="text-bad">Could not load accounts: {error}</p>}
      <div className="flex flex-col gap-4 lg:flex-row">
        <div className="min-w-0 flex-1">
          <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full rounded-lg bg-ink/60">
            <defs>
              {(Object.keys(KIND_COLOR) as Kind[]).map((k) => (
                <marker key={k} id={`arrow-${k}`} viewBox="0 0 10 10" refX="24" refY="5" markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
                  <path d="M0,0 L10,5 L0,10 z" fill={KIND_COLOR[k]} />
                </marker>
              ))}
            </defs>
            <text x={W * 0.3} y={20} textAnchor="middle" className="fill-muted text-[11px] uppercase tracking-wider">testnet: agent payments</text>
            <text x={W * 0.72} y={20} textAnchor="middle" className="fill-muted text-[11px] uppercase tracking-wider">devnet: lending desk</text>
            {edges.map((e) => {
              const a = pos(e.from);
              const b = pos(e.to);
              if (!a || !b) return null;
              const pulse = pulses.current.get(e.key);
              const hot = pulse !== undefined && now - pulse < PULSE_MS;
              const href = e.lastHash ? `${EXPLORER[e.network]}/transactions/${e.lastHash}` : undefined;
              // Edges between the same two nodes bend apart so an auto and a refused flow do not overlap.
              const pair = edges.filter((o) => (o.from === e.from && o.to === e.to) || (o.from === e.to && o.to === e.from));
              const bend = (pair.indexOf(e) - (pair.length - 1) / 2) * 28 * (e.from < e.to ? 1 : -1);
              const [ax, ay, bx, by] = [a.x ?? 0, a.y ?? 0, b.x ?? 0, b.y ?? 0];
              const len = Math.hypot(bx - ax, by - ay) || 1;
              const cx = (ax + bx) / 2 - ((by - ay) / len) * bend;
              const cy = (ay + by) / 2 + ((bx - ax) / len) * bend;
              const line = (
                <path
                  d={`M${ax},${ay} Q${cx},${cy} ${bx},${by}`}
                  fill="none"
                  stroke={KIND_COLOR[e.kind]}
                  strokeWidth={width(e.drops) + (hot ? 4 : 0)}
                  strokeOpacity={hot ? 1 : 0.7}
                  strokeDasharray={e.kind === "refused" ? "6 5" : hot ? "10 6" : undefined}
                  className={hot ? "flow-pulse" : undefined}
                  markerEnd={`url(#arrow-${e.kind})`}
                >
                  <title>{`${KIND_LABEL[e.kind]}: ${e.count} tx, ${(e.drops / 1e6).toLocaleString()} XRP total${e.lastHash ? `\nlast tx ${e.lastHash}` : ""}`}</title>
                </path>
              );
              return href ? (
                <a key={e.key} href={href} target="_blank" rel="noreferrer" className="cursor-pointer">
                  {line}
                </a>
              ) : (
                <g key={e.key}>{line}</g>
              );
            })}
            {nodes.map((n) => {
              const p = pos(n.id);
              if (!p) return null;
              const href = n.id.startsWith("vault:") ? undefined : `${EXPLORER[n.network]}/accounts/${n.id}`;
              const body = (
                <g transform={`translate(${p.x},${p.y})`}>
                  <circle r={n.role === "treasury" || n.role === "vault" ? 16 : 11} fill={ROLE_COLOR[n.role]} fillOpacity={0.9} stroke="#0f1419" strokeWidth={2} />
                  <text y={n.role === "treasury" || n.role === "vault" ? 30 : 25} textAnchor="middle" className="fill-fg text-[11px]">
                    {n.name}
                  </text>
                  <title>{`${n.name} (${n.role}, ${n.network})\n${n.id}`}</title>
                </g>
              );
              return href ? (
                <a key={n.id} href={href} target="_blank" rel="noreferrer" className="cursor-pointer">
                  {body}
                </a>
              ) : (
                <g key={n.id}>{body}</g>
              );
            })}
          </svg>
          <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
            {(Object.keys(KIND_COLOR) as Kind[]).map((k) => (
              <span key={k} className="flex items-center gap-1">
                <span className="inline-block h-0.5 w-5" style={{ background: KIND_COLOR[k], borderTop: k === "refused" ? `2px dashed ${KIND_COLOR[k]}` : undefined }} />
                {KIND_LABEL[k]}
              </span>
            ))}
            <span>· width = amount · click a node for the account, an edge for its latest tx</span>
          </div>
        </div>
        <aside className="w-full shrink-0 lg:w-80">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Ticker</h3>
            <div className="flex gap-1 text-xs">
              {(["latest", "all"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setScope(s)}
                  className={`rounded px-2 py-0.5 ${scope === s ? "bg-accent/20 text-fg" : "text-muted hover:text-fg"}`}
                  title={s === "latest" ? "Each network's last run (15 min before its newest flow); device and RPC incidents hidden" : "Everything, including device and RPC incidents"}
                >
                  {s === "latest" ? "Latest run" : "All"}
                </button>
              ))}
            </div>
          </div>
          <ol className="max-h-[520px] space-y-1 overflow-y-auto pr-1 text-xs">
            {flows.slice(0, 40).map((f) => (
              <li key={f.id} className={`rounded-md bg-ink/50 px-2 py-1.5 ${now - f.ts < 15000 ? "fade-in ring-1 ring-accent/50" : ""}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold" style={{ color: KIND_COLOR[f.kind] }}>
                    {KIND_LABEL[f.kind]}
                    {f.note && f.kind !== "refused" ? ` · ${f.note}` : ""}
                  </span>
                  <span className="tabular-nums">{f.amount}</span>
                </div>
                <div className="truncate text-muted">
                  {nameOf(nodes, f.from)} → {nameOf(nodes, f.to)} · {f.network}
                </div>
                <div className="font-mono">
                  {f.hash ? (
                    <a className="text-accent hover:underline" href={`${EXPLORER[f.network]}/transactions/${f.hash}`} target="_blank" rel="noreferrer">
                      {shortHash(f.hash)}
                    </a>
                  ) : (
                    <span className="text-bad">{f.note ?? "refused"}: never reached the ledger</span>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </section>
  );
}

function nameOf(nodes: GraphNode[], id: string): string {
  return nodes.find((n) => n.id === id)?.name ?? shortAccount(id);
}
