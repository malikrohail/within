// Live testnet check of the credential module the server uses (npm run test:live, not part of npm test).
// Fresh faucet issuer and subject; never the hot account, never the running wallet.
import { afterAll, beforeAll, expect, it } from "vitest";
import { Client, Wallet, type CredentialAccept } from "xrpl";
import { clientCredentialRpc, credentialTypeHex, Credentials } from "../../src/credentials.js";
import { XrplConnection } from "../../src/xrpl.js";

const XRPL_WSS = process.env.XRPL_WSS ?? "wss://s.altnet.rippletest.net:51233";
const TYPE = "x402-merchant";
const explorer = (hash: string | null) => `https://testnet.xrpl.org/transactions/${hash}`;

const xrpl = new XrplConnection(XRPL_WSS, () => {});
let client: Client;
let issuer: Wallet;
let subject: Wallet;
let creds: Credentials;

beforeAll(async () => {
  client = await xrpl.get();
  [{ wallet: issuer }, { wallet: subject }] = await Promise.all([client.fundWallet(Wallet.generate()), client.fundWallet(Wallet.generate())]);
  console.log(`issuer=${issuer.classicAddress} subject=${subject.classicAddress}`);
  creds = new Credentials(clientCredentialRpc(xrpl), issuer);
}, 120_000);
afterAll(() => xrpl.close());

it("create → not accepted → accept → credentialed → delete → not credentialed", async () => {
  const s = subject.classicAddress;
  const i = issuer.classicAddress;

  const created = await creds.create(s, TYPE);
  console.log(`CredentialCreate ${created.engineResult} ${explorer(created.txHash)}`);
  expect(created.engineResult).toBe("tesSUCCESS");
  expect((await creds.create(s, TYPE)).engineResult).toBe("tecDUPLICATE");
  expect(await creds.check(s, i, TYPE)).toBe(false);
  expect(await creds.list(i, TYPE)).toEqual([{ address: s, accepted: false, txHash: created.txHash }]);

  // The merchant's side (agent/merchants does this at startup); the wallet never sends it.
  const accept: CredentialAccept = { TransactionType: "CredentialAccept", Account: s, Issuer: i, CredentialType: credentialTypeHex(TYPE) };
  const accepted = await client.submitAndWait(accept, { autofill: true, wallet: subject });
  console.log(`CredentialAccept ${(accepted.result.meta as { TransactionResult: string }).TransactionResult} ${explorer(accepted.result.hash)}`);
  expect(await creds.check(s, i, TYPE)).toBe(false); // still the cached answer
  creds.forget(s);
  expect(await creds.check(s, i, TYPE)).toBe(true);
  expect(await creds.list(i, TYPE)).toEqual([{ address: s, accepted: true, txHash: accepted.result.hash }]);

  const deleted = await creds.remove(s, TYPE);
  console.log(`CredentialDelete ${deleted.engineResult} ${explorer(deleted.txHash)}`);
  expect(deleted.engineResult).toBe("tesSUCCESS");
  expect(await creds.check(s, i, TYPE)).toBe(false); // remove() cleared the cache
  expect(await creds.list(i, TYPE)).toEqual([]);
  expect((await creds.remove(s, TYPE)).engineResult).toBe("tecNO_ENTRY");
}, 180_000);
