import type { DeviceManagementKit } from "@ledgerhq/device-management-kit";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LedgerDevice } from "../src/device.js";

afterEach(() => vi.useRealTimers());

describe("LedgerDevice session handling", () => {
  it("closes the old DMK session when it marks the device disconnected, so no leaked session polls the app", async () => {
    vi.useFakeTimers(); // the 5 s reconnect timer must not fire
    const disconnect = vi.fn(async () => {});
    const device = new LedgerDevice("http://127.0.0.1:5000", () => {}, { disconnect } as unknown as DeviceManagementKit);
    const internals = device as unknown as { sessionId: string | null; info: { connected: boolean }; markDisconnected: (why: string) => void };
    internals.sessionId = "session-1";
    internals.info.connected = true;
    internals.markDisconnected("session state");
    expect(disconnect).toHaveBeenCalledWith({ sessionId: "session-1" });
    expect(device.status().connected).toBe(false);
    internals.markDisconnected("again"); // no session left: nothing more to close
    expect(disconnect).toHaveBeenCalledTimes(1);
  });
});
