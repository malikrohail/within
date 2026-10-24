import { afterEach, describe, expect, it, vi } from "vitest";
import type { Client } from "xrpl";
import { isConnectionError, XrplConnection } from "../src/xrpl.js";

/** A fake xrpl Client: `fail` makes its requests throw the given error. */
function fakeClient(n: number, fail?: Error) {
  let connected = false;
  return {
    n,
    disconnects: 0,
    on: vi.fn(),
    isConnected: () => connected,
    connect: vi.fn(async () => void (connected = true)),
    disconnect: vi.fn(async function (this: { disconnects: number }) {
      connected = false;
    }),
    request: vi.fn(async (req: { command: string }) => {
      if (fail) throw fail;
      return { result: { from: n, command: req.command } };
    }),
  };
}

const neverCleanedUp = Object.assign(new Error("Websocket connection never cleaned up."), { name: "ConnectionError" });

afterEach(() => vi.useRealTimers());

describe("isConnectionError", () => {
  it("matches socket failures, not rippled answers", () => {
    expect(isConnectionError(neverCleanedUp)).toBe(true);
    expect(isConnectionError(Object.assign(new Error("Timeout for request: {...}"), { name: "TimeoutError" }))).toBe(true);
    expect(isConnectionError(Object.assign(new Error("entryNotFound"), { name: "RippledError" }))).toBe(false);
  });
});

describe("XrplConnection", () => {
  it("reconnects with a fresh client and retries a read once after a dead socket", async () => {
    const clients = [fakeClient(1, neverCleanedUp), fakeClient(2)];
    const logs: string[] = [];
    const conn = new XrplConnection("wss://x", (m) => logs.push(m), () => clients.shift() as unknown as Client);
    const r = await conn.read((c) => c.request({ command: "ping" }));
    expect(r.result).toMatchObject({ from: 2 });
    expect(logs.join("\n")).toMatch(/xrpl reconnect: Websocket connection never cleaned up\.; retrying once/);
  });

  it("does not retry an answer from rippled", async () => {
    const make = vi.fn(() => fakeClient(1, Object.assign(new Error("entryNotFound"), { name: "RippledError" })) as unknown as Client);
    const conn = new XrplConnection("wss://x", () => {}, make);
    await expect(conn.read((c) => c.request({ command: "ping" }))).rejects.toThrow("entryNotFound");
    expect(make).toHaveBeenCalledTimes(1);
  });

  it("gives up after one retry (the caller fails closed)", async () => {
    const make = vi.fn(() => fakeClient(1, neverCleanedUp) as unknown as Client);
    const conn = new XrplConnection("wss://x", () => {}, make);
    await expect(conn.read((c) => c.request({ command: "ping" }))).rejects.toThrow("never cleaned up");
    expect(make).toHaveBeenCalledTimes(2);
  });

  it("opens a new client when the current one reports disconnected", async () => {
    const first = fakeClient(1);
    const clients = [first, fakeClient(2)];
    const conn = new XrplConnection("wss://x", () => {}, () => clients.shift() as unknown as Client);
    await conn.get();
    await first.disconnect();
    expect(((await conn.read((c) => c.request({ command: "ping" }))).result as { from: number }).from).toBe(2);
  });

  it("watchdog reconnects after a wake (wall-clock jump) and after a failed ping", async () => {
    vi.useFakeTimers();
    const clients = [fakeClient(1), fakeClient(2, new Error("Timeout for request")), fakeClient(3)];
    const logs: string[] = [];
    const conn = new XrplConnection("wss://x", (m) => logs.push(m), () => clients.shift() as unknown as Client);
    await conn.get();
    const timer = conn.watchdog(5_000, 6);

    vi.setSystemTime(Date.now() + 120_000); // the Mac slept two minutes
    await vi.advanceTimersByTimeAsync(5_000);
    expect(logs.at(-1)).toMatch(/xrpl reconnect: wake detected \(process paused ~12\d s\)/);

    await conn.get(); // client 2, whose ping fails
    await vi.advanceTimersByTimeAsync(30_000);
    expect(logs.at(-1)).toMatch(/xrpl reconnect: watchdog ping failed: Timeout for request/);
    expect(((await conn.read((c) => c.request({ command: "ping" }))).result as { from: number }).from).toBe(3);
    clearInterval(timer);
  });
});
