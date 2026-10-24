// Metadata files for the lending-era types and Batch (format/).
import Batch from "../format/Batch.json" with { type: "json" };
import LoanBrokerSet from "../format/LoanBrokerSet.json" with { type: "json" };
import LoanManage from "../format/LoanManage.json" with { type: "json" };
import LoanPay from "../format/LoanPay.json" with { type: "json" };
import LoanSet from "../format/LoanSet.json" with { type: "json" };
import PermissionedDomainSet from "../format/PermissionedDomainSet.json" with { type: "json" };
import VaultCreate from "../format/VaultCreate.json" with { type: "json" };
import VaultDeposit from "../format/VaultDeposit.json" with { type: "json" };
import VaultWithdraw from "../format/VaultWithdraw.json" with { type: "json" };
import type { Descriptor } from "./types.js";

export const LENDING_DESCRIPTORS = [
  VaultCreate, VaultDeposit, VaultWithdraw, LoanBrokerSet, LoanSet, LoanPay, LoanManage, PermissionedDomainSet, Batch,
] as Descriptor[];
