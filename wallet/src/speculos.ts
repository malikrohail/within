// Drives the Speculos emulator's REST API (contract: POST /v1/requests/:id/device-tap and /deny).
const realSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export class Speculos {
  /** `sleep` is injectable so tests can drive the tap recipe without real delays. */
  constructor(
    readonly url: string,
    private readonly sleep: (ms: number) => Promise<void> = realSleep,
  ) {}

  async finger(action: "press-and-release" | "press" | "release", x: number, y: number): Promise<void> {
    const res = await fetch(`${this.url}/finger`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, x, y }),
    });
    await res.arrayBuffer();
    if (!res.ok) throw new Error(`speculos /finger ${res.status}`);
  }

  /** Clears the event history. The DMK transport polls GET /events (full history) without reading it. */
  async clearEvents(): Promise<void> {
    await (await fetch(`${this.url}/events`, { method: "DELETE" })).arrayBuffer();
  }

  async screenText(): Promise<string[]> {
    const res = await fetch(`${this.url}/events?currentscreenonly=true`);
    const body = (await res.json()) as { events: { text: string }[] };
    return body.events.map((e) => e.text);
  }

  /** Current-screen text with positions, for tapping a control by its label. */
  async screenEvents(): Promise<ScreenEvent[]> {
    const res = await fetch(`${this.url}/events?currentscreenonly=true`);
    return ((await res.json()) as { events: ScreenEvent[] }).events;
  }

  /** Taps the first control whose trimmed label matches. False if none is on screen. */
  private async tapText(re: RegExp): Promise<boolean> {
    const e = (await this.screenEvents()).find((ev) => re.test(ev.text.trim()));
    if (!e) return false;
    await this.finger("press-and-release", Math.round(e.x + Math.min(e.w, 200) / 2), Math.round(e.y + e.h / 2));
    return true;
  }

  private async screenHas(re: RegExp): Promise<boolean> {
    return (await this.screenText()).some((t) => re.test(t));
  }

  /**
   * Contract tap recipe, adapted to the page count: "next" at (350,620) 700 ms apart until the
   * "Hold to sign" page shows (2 taps for a bare Payment, 4 with x402 memos), then hold (336,515) 3 s.
   */
  async approve(log: (msg: string) => void = () => {}, isDone: () => boolean = () => false): Promise<void> {
    let taps = 0;
    while (taps < 8 && !(await this.screenHas(/hold to sign/i))) {
      // A blind-signed type (DelegateSet on XRP app 2.8.1) opens with "Blind signing ahead".
      if (await this.screenHas(/continue anyway/i)) {
        await this.tapText(/^continue anyway$/i);
        log("blind-signing warning: tapped Continue anyway");
      } else await this.finger("press-and-release", 350, 620);
      taps++;
      await this.sleep(700);
    }
    log(`next taps sent=${taps} screen=${JSON.stringify(await this.screenText())}`);
    // A press can be lost (e.g. the Mac slept mid-hold): press once more only if, 2 s after release,
    // the request is still unresolved and the sign page is still up (the screen text lags the signature).
    for (let press = 1; press <= 2; press++) {
      await this.finger("press", 336, 515);
      log(`hold pressed (attempt ${press})`);
      await this.sleep(3000);
      await this.finger("release", 336, 515);
      let screen: string[] = [];
      for (let i = 0; i < 8; i++) {
        await this.sleep(250);
        screen = await this.screenText();
        if (isDone() || !screen.some((t) => /hold to sign/i.test(t))) break;
      }
      log(`hold released screen=${JSON.stringify(screen)}${isDone() ? " (request resolved)" : ""}`);
      if (isDone() || !screen.some((t) => /hold to sign/i.test(t))) return;
    }
  }

  /** Waits until a transaction review (or its reject confirmation) is on screen, or gives up after timeoutMs. */
  async waitForReview(timeoutMs: number): Promise<boolean> {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
      if (await this.screenHas(REVIEW)) return true;
      await this.sleep(250);
    }
    return false;
  }

  /**
   * Reject from any review page (including the sign page) or a half-done reject confirmation:
   * Reject at (80,625), then "Yes, reject" at (200,540), until no review is on screen (3 attempts).
   * Resolves true once the review is gone.
   */
  async reject(log: (msg: string) => void = () => {}): Promise<boolean> {
    for (let attempt = 1; attempt <= 3; attempt++) {
      // Blind-signing pages: "Back to safety" on the warning, "Reject transaction" on the
      // "cannot be clear-signed" page (blind signing off), which stays up after the APDU failed.
      if (await this.screenHas(/back to safety/i)) {
        await this.tapText(/^back to safety$/i);
        await this.sleep(700);
      } else if (await this.screenHas(/cannot be clear-/i)) {
        await this.tapText(/^reject transaction$/i);
        await this.sleep(700);
      } else if (!(await this.screenHas(/yes, reject/i))) {
        await this.finger("press-and-release", 80, 625);
        await this.sleep(700);
      }
      if (await this.screenHas(/yes, reject/i)) await this.finger("press-and-release", 200, 540);
      for (let i = 0; i < 12; i++) {
        await this.sleep(250);
        if (!(await this.screenHas(REVIEW))) {
          log(`reject attempt ${attempt}: review gone, screen=${JSON.stringify(await this.screenText())}`);
          return true;
        }
      }
      log(`reject attempt ${attempt}: review still on screen ${JSON.stringify(await this.screenText())}`);
    }
    return false;
  }
}

// "2 of 3": a review detail page (it names no action), e.g. when someone stepped through by hand.
const REVIEW = /review transaction|sign transaction\?|hold to sign|reject transaction\?|blind signing ahead|cannot be clear-|^\d+ of \d+$/i;

export type ScreenEvent = { text: string; x: number; y: number; w: number; h: number };

/**
 * The DMK Speculos transport polls GET /events (the whole event history) every few seconds with
 * responseType "void" and never reads the body. Speculos (Werkzeug) answers `Connection: close`, and
 * once the unread body passes ~64 KB Node's undici hits `assert(!this.paused)` in Parser.finish and
 * the process dies. Wrap the global fetch so every Speculos response (except the SSE stream) is
 * read in full before the caller gets it.
 */
export function drainSpeculosResponses(speculosUrl: string): void {
  const origin = new URL(speculosUrl).origin;
  const original = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const res = await original(input, init);
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (!url.startsWith(origin) || url.includes("stream=true")) return res;
    const body = res.status === 204 || res.status === 304 ? null : await res.arrayBuffer();
    return new Response(body, { status: res.status, statusText: res.statusText, headers: res.headers });
  };
}
