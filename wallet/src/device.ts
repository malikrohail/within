import {
  DeviceActionStatus,
  DeviceManagementKitBuilder,
  DeviceModelId,
  DeviceStatus,
  UserInteractionRequired,
  hexaStringToBuffer,
  type DeviceManagementKit,
  type DeviceSessionId,
} from "@ledgerhq/device-management-kit";
import { SignerXrpBuilder, type SignerXrp } from "@ledgerhq/device-signer-kit-xrp";
import { speculosIdentifier, speculosTransportFactory } from "@ledgerhq/device-transport-kit-speculos";
import { firstValueFrom, timeout } from "rxjs";

export const DERIVATION_PATH = "44'/144'/0'/0/0";

export type DeviceStatusInfo = { connected: boolean; address: string | null; publicKey: string | null; app: string | null };

export type DeviceSignAction = {
  /** DER signature. Rejects with DeviceError. */
  result: Promise<Uint8Array>;
  /** Resolves once the review is waiting for the user on the device. */
  onScreen: Promise<void>;
  cancel(): void;
};

export class DeviceError extends Error {
  constructor(readonly code: "rejected_on_device" | "device_unavailable" | "stopped", detail?: string) {
    super(detail ? `${code}: ${detail}` : code);
  }
}

export interface DeviceSigner {
  status(): DeviceStatusInfo;
  sign(unsignedTxHex: string): DeviceSignAction;
}

/** Ledger over the DMK Speculos transport. Connects at boot, retries every 5 s, never throws out. */
export class LedgerDevice implements DeviceSigner {
  private dmk: DeviceManagementKit;
  private signer: SignerXrp | null = null;
  private sessionId: DeviceSessionId | null = null;
  private info: DeviceStatusInfo = { connected: false, address: null, publicKey: null, app: null };
  private retry: NodeJS.Timeout | null = null;

  constructor(speculosUrl: string, private readonly log: (msg: string) => void = console.log, dmk?: DeviceManagementKit) {
    this.dmk =
      dmk ??
      new DeviceManagementKitBuilder()
        // Real device over USB: .addTransport(nodeHidTransportFactory) from @ledgerhq/device-transport-kit-node-hid (out of scope).
        .addTransport(speculosTransportFactory(speculosUrl, false, DeviceModelId.STAX))
        .build();
  }

  start(): void {
    void this.connect();
  }

  status(): DeviceStatusInfo {
    return { ...this.info };
  }

  private scheduleRetry(): void {
    if (this.retry) return;
    this.retry = setTimeout(() => {
      this.retry = null;
      void this.connect();
    }, 5000);
  }

  private markDisconnected(why: string): void {
    if (this.info.connected) this.log(`device disconnected (${why}); retrying every 5 s`);
    // Close the old session before the retry opens a new one. A leaked session keeps polling the app,
    // and the app answers our next sign with 6901 (busy), as with two DMK clients (DX finding 9).
    if (this.sessionId) this.dmk.disconnect({ sessionId: this.sessionId }).catch(() => {});
    this.info = { ...this.info, connected: false };
    this.signer = null;
    this.sessionId = null;
    this.scheduleRetry();
  }

  private async connect(): Promise<void> {
    try {
      const device = await firstValueFrom(this.dmk.startDiscovering({ transport: speculosIdentifier }).pipe(timeout(5000)));
      await this.dmk.stopDiscovering();
      const sessionId = await this.dmk.connect({ device });
      const signer = new SignerXrpBuilder({ dmk: this.dmk, sessionId }).build();
      const { address, publicKey } = await runAction(signer.getAddress(DERIVATION_PATH, { checkOnDevice: false }));
      this.signer = signer;
      this.sessionId = sessionId;
      this.info = { connected: true, address, publicKey: publicKey.toUpperCase(), app: this.info.app };
      this.log(`device connected address=${address}`);
      this.dmk.getDeviceSessionState({ sessionId }).subscribe({
        next: (s) => {
          if (this.sessionId !== sessionId) return; // a closed session must not tear down its replacement
          if (s.deviceStatus === DeviceStatus.NOT_CONNECTED) return this.markDisconnected("session state");
          if ("currentApp" in s && s.currentApp) this.info.app = `${s.currentApp.name} ${s.currentApp.version}`;
        },
        error: () => this.sessionId === sessionId && this.markDisconnected("session error"),
        complete: () => this.sessionId === sessionId && this.markDisconnected("session closed"),
      });
    } catch (e) {
      this.markDisconnected(String((e as Error)?.message ?? e));
    }
  }

  sign(unsignedTxHex: string): DeviceSignAction {
    if (!this.signer) {
      const err = Promise.reject(new DeviceError("device_unavailable"));
      err.catch(() => {});
      return { result: err, onScreen: new Promise(() => {}), cancel: () => {} };
    }
    const { observable, cancel } = this.signer.signTransaction(DERIVATION_PATH, hexaStringToBuffer(unsignedTxHex)!);
    let markOnScreen!: () => void;
    const onScreen = new Promise<void>((r) => (markOnScreen = r));
    const result = new Promise<Uint8Array>((resolve, reject) => {
      let last = "";
      observable.subscribe({
        next: (s) => {
          const step = `${s.status}${s.status === DeviceActionStatus.Pending ? `/${s.intermediateValue?.requiredUserInteraction}` : ""}`;
          if (step !== last) this.log(`device sign status=${(last = step)}${s.status === DeviceActionStatus.Error ? ` error=${toDeviceError(s.error).message}` : ""}`);
          if (s.status === DeviceActionStatus.Pending && s.intermediateValue?.requiredUserInteraction === UserInteractionRequired.SignTransaction) markOnScreen();
          else if (s.status === DeviceActionStatus.Completed) resolve(s.output);
          else if (s.status === DeviceActionStatus.Error) reject(toDeviceError(s.error));
          else if (s.status === DeviceActionStatus.Stopped) reject(new DeviceError("stopped"));
        },
        error: (e) => reject(toDeviceError(e)),
        complete: () => reject(new DeviceError("stopped")),
      });
    });
    return { result, onScreen, cancel };
  }
}

function toDeviceError(e: unknown): DeviceError {
  const code = (e as { errorCode?: string })?.errorCode;
  if (code === "6985") return new DeviceError("rejected_on_device");
  const sw = (e as { originalError?: { errorCode?: string } })?.originalError?.errorCode;
  return new DeviceError("device_unavailable", `${String((e as Error)?.message ?? (e as { _tag?: string })?._tag ?? e)}${sw ? ` (status ${sw})` : ""}`);
}

/** Runs a DMK device action to completion. */
function runAction<T>(action: { observable: import("rxjs").Observable<{ status: DeviceActionStatus; output?: T; error?: unknown }> }): Promise<T> {
  return new Promise((resolve, reject) => {
    action.observable.subscribe({
      next: (s) => {
        if (s.status === DeviceActionStatus.Completed) resolve(s.output as T);
        else if (s.status === DeviceActionStatus.Error) reject(toDeviceError(s.error));
        else if (s.status === DeviceActionStatus.Stopped) reject(new DeviceError("stopped"));
      },
      error: (e) => reject(toDeviceError(e)),
    });
  });
}
