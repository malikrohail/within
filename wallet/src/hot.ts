import { Wallet, hashes, type Payment } from "xrpl";
import type { SignedTx } from "./types.js";

export class HotKey {
  readonly wallet: Wallet;

  constructor(seed: string) {
    this.wallet = Wallet.fromSeed(seed);
  }

  get address(): string {
    return this.wallet.classicAddress;
  }

  sign(tx: Payment): SignedTx {
    const { tx_blob } = this.wallet.sign(tx);
    return { blob: tx_blob, hash: hashes.hashSignedTx(tx_blob) };
  }
}
