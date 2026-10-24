import { readFileSync } from "node:fs";
import { describe, type Preview } from "../src/index.js";

export const NAMES = {
  rUPNkALm4H4xefrVziYPxPARi1t6knrm7m: "agent (hot key)",
  rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B: "treasury (Ledger)",
  rwKL4Bir4ED8jbMheyMGMnTWyeUcL3VpCa: "good merchant",
};
export const NOW = Date.parse("2026-10-24T14:00:00Z");

/** Loads test/fixtures/<dir>/<name>.json (real ones carry _source with the hash; synthetic ones carry _synthetic). */
export function fixture(dir: "testnet" | "devnet" | "synthetic", name: string): Record<string, unknown> {
  const f = JSON.parse(readFileSync(new URL(`./fixtures/${dir}/${name}.json`, import.meta.url), "utf8"));
  if (dir !== "synthetic" && !f._source?.validated) throw new Error(`${name}: real fixture without a validated _source`);
  return f.tx_json;
}

export const card = (tx: Record<string, unknown>): Preview => describe(tx, { names: NAMES, now: NOW });
export const line = (p: Preview, label: string) => p.lines.find((l) => l.label === label);
export const risks = (p: Preview) => p.lines.filter((l) => l.label === "Risk").map((l) => l.risk);
