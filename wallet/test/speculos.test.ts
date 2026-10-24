import net from "node:net";
import { afterAll, describe, expect, it } from "vitest";
import { drainSpeculosResponses, Speculos } from "../src/speculos.js";

// Mimics Speculos (Werkzeug): Connection: close and a large GET /events body that the DMK never reads.
// Without the drain, Node's undici hits assert(!this.paused) in Parser.finish and kills the process.
const BODY = "x".repeat(100_000);
const server = net.createServer((s) =>
  s.once("data", () => {
    s.write(`HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${BODY.length}\r\nConnection: close\r\n\r\n`);
    s.end(BODY);
  }),
);
const original = globalThis.fetch;
afterAll(() => {
  globalThis.fetch = original;
  server.close();
});

describe("drainSpeculosResponses", () => {
  it("survives unread close-delimited bodies and still returns them", async () => {
    await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
    const url = `http://127.0.0.1:${(server.address() as net.AddressInfo).port}`;
    drainSpeculosResponses(url);
    for (let i = 0; i < 5; i++) {
      const res = await fetch(`${url}/events`); // body deliberately not read, like responseType "void"
      expect(res.status).toBe(200);
      await new Promise((r) => setTimeout(r, 200));
    }
    expect((await (await fetch(`${url}/events`)).text()).length).toBe(BODY.length);
  });
});

/** Screen state machine for a Stax review: review pages → sign page → confirm reject → home. */
class FakeStax extends Speculos {
  screen: string[] = ["Sign transaction?", "Reject", "4 of 4", "Hold to sign"];
  ignoreTaps = 0;
  lostPresses = 0;
  constructor() {
    super("http://fake", async () => {});
  }
  async finger(action: "press-and-release" | "press" | "release", x: number, y: number): Promise<void> {
    if (this.ignoreTaps > 0) return void this.ignoreTaps--;
    const s = this.screen.join("|");
    if (action === "press-and-release" && x === 80 && /Reject/.test(s) && !/Yes, reject/.test(s)) this.screen = ["Reject transaction?", "Go back to transaction", "Yes, reject"];
    else if (action === "press-and-release" && y === 540 && /Yes, reject/.test(s)) this.screen = ["Transaction rejected"];
    else if (action === "release" && /Hold to sign/.test(s)) {
      if (this.lostPresses > 0) this.lostPresses--;
      else this.screen = ["Transaction signed"];
    }
  }
  async screenText(): Promise<string[]> {
    return this.screen;
  }
}

describe("Speculos driver", () => {
  it("rejects from the sign page and confirms the review is gone", async () => {
    const stax = new FakeStax();
    const logs: string[] = [];
    expect(await stax.reject((m) => logs.push(m))).toBe(true);
    expect(stax.screen).toEqual(["Transaction rejected"]);
    expect(logs[0]).toMatch(/reject attempt 1: review gone/);
  });

  it("finishes a half-done reject from the confirmation screen", async () => {
    const stax = new FakeStax();
    stax.screen = ["Reject transaction?", "Go back to transaction", "Yes, reject"];
    expect(await stax.reject()).toBe(true);
  });

  it("retries a reject whose first tap was lost, and reports failure after 3 attempts", async () => {
    const stax = new FakeStax();
    stax.ignoreTaps = 1;
    expect(await stax.reject()).toBe(true);
    const stuck = new FakeStax();
    stuck.ignoreTaps = 99;
    expect(await stuck.reject()).toBe(false);
  });

  it("counts a review detail page (\"2 of 3\") as a review on screen, so Approve and cleanup still act", async () => {
    const stax = new FakeStax();
    stax.screen = ["Transaction Type", "Unknown", "Authorize", "rUPNkA", "Unknown [1]", "1", "Reject", "2 of 3"];
    expect(await stax.waitForReview(10)).toBe(true);
    expect(await stax.reject()).toBe(true);
    expect(stax.screen).toEqual(["Transaction rejected"]);
  });

  it("presses hold to sign again when the first press was lost", async () => {
    const stax = new FakeStax();
    stax.lostPresses = 1;
    const logs: string[] = [];
    await stax.approve((m) => logs.push(m));
    expect(stax.screen).toEqual(["Transaction signed"]);
    expect(logs.filter((l) => l.startsWith("hold pressed"))).toEqual(["hold pressed (attempt 1)", "hold pressed (attempt 2)"]);
  });

  it("does not press again once the request has resolved, even if the screen text lags", async () => {
    const stax = new FakeStax();
    stax.lostPresses = 1; // the screen still shows the sign page after the first release
    const logs: string[] = [];
    await stax.approve((m) => logs.push(m), () => true);
    expect(logs.filter((l) => l.startsWith("hold pressed"))).toEqual(["hold pressed (attempt 1)"]);
    expect(logs.at(-1)).toMatch(/\(request resolved\)/);
  });
});
