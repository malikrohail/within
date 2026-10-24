// Metadata files for the core types (format/).
import AccountSet from "../format/AccountSet.json" with { type: "json" };
import CredentialAccept from "../format/CredentialAccept.json" with { type: "json" };
import CredentialCreate from "../format/CredentialCreate.json" with { type: "json" };
import CredentialDelete from "../format/CredentialDelete.json" with { type: "json" };
import DelegateSet from "../format/DelegateSet.json" with { type: "json" };
import EscrowCancel from "../format/EscrowCancel.json" with { type: "json" };
import EscrowCreate from "../format/EscrowCreate.json" with { type: "json" };
import EscrowFinish from "../format/EscrowFinish.json" with { type: "json" };
import Payment from "../format/Payment.json" with { type: "json" };
import SignerListSet from "../format/SignerListSet.json" with { type: "json" };
import type { Descriptor } from "./types.js";

export const CORE_DESCRIPTORS = [
  Payment, CredentialCreate, CredentialAccept, CredentialDelete, DelegateSet, AccountSet, SignerListSet, EscrowCreate, EscrowFinish, EscrowCancel,
] as Descriptor[];
