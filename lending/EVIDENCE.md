# Lending Desk — raw devnet evidence

Generated 2026-10-24T22:09:03Z by `lending/make_evidence.py`; every tx and object below was re-read from devnet (`https://s.devnet.rippletest.net:51234/`) at that time. Long hex is trimmed; seeds never appear.

**Why tecTOO_SOON and tecEXPIRED appear below:** the vault is close-ended (`VaultKind` 1). Before its `SubscriptionDate` it is raising funds: `VaultDeposit` succeeds and `LoanSet` is rejected `tecTOO_SOON`. After that date it is lending: `LoanSet` succeeds and a late `VaultDeposit` is rejected `tecEXPIRED`. Each scripted demo run opens a new vault with a ~120 s subscription window, takes the deposits inside it, then lends.

**Scripted run switches:** the pre-staged 9/9 ran with the approver gate and the second opinion off (`DESK_APPROVER_ACCOUNT=off SECOND_OPINION=off`), because a fresh account with 22 memo-dated active days is exactly what the model should flag; the stage's live held request runs with both ON.

**Cover units:** LoanBroker rates are in 1/100,000 (10000 = 10 %). On a default the ledger takes `DebtTotal x CoverRateMinimum x CoverRateLiquidation` from first-loss cover. With 10 % x 100 % that is 10 % of the debt (cover 20 -> 14 XRP on a 60 XRP default in the batch spike below). Runs before this change used liquidation 10000, i.e. 1 % (20 -> 19.33 XRP).

## Accounts and ids
```json
{
  "network": "devnet",
  "accounts": {
    "broker": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "depositorA": "rKecLpa298P3oLJox7zKb6sTfBa9aG2ZjL",
    "depositorB": "rNqeTV1TD32ZzpFX2zAeWnMtLjfgyujKLW",
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "supplier": "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai",
    "customer": "rByBccT5CSXGuC1LnxiNtzaXYjGZm3MTq1"
  },
  "vaultId": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
  "shareMptId": "000000018EA2EBED47631F388C34082D16CBCA900BF07116",
  "loanBrokerId": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
  "vaultKind": "closed",
  "subscriptionDate": 1792874121,
  "redemptionDate": 1792902801,
  "history": {
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "customers": [
      "rKUKmQ2ZnAQCh24UBDXR89u81SkviJxS4M",
      "rE8RjsX4W1gk63kr6friMvTYDGi1mEMSFq",
      "r32nDoAxX8YVdNzu48oPT5bgXvNMAC5trQ",
      "rhJHWDJZaXRxJ7dw8RxGQdADNCbHjsrDb6",
      "rDn6n2SCMKNMMjqMZBSTxQdxt89wGDNuTg"
    ],
    "paymentCount": 24,
    "volumeDrops": "61000000",
    "activeDays": 22,
    "topPayerSharePct": 31.1,
    "firstHash": "8BCBA088A6FFE74F8C43A6832EE6F7C0E5EC61920DDDED4E06C80E1381568302",
    "lastHash": "778665100D899A6221732682FC403A54CC8F08E09414A11040EC3BA592ED8E3C",
    "seededAt": 1792874451
  }
}
```
## Setup transactions (M1)
### vaultCreate
- hash: [`7212DD8BA03EA1201A95562DEC5CCEEE471542F74B6BF98760F0B1002A114313`](https://devnet.xrpl.org/transactions/7212DD8BA03EA1201A95562DEC5CCEEE471542F74B6BF98760F0B1002A114313)
- validated: `True`, ledger `6387586`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
  "Asset": {
    "currency": "XRP"
  },
  "Fee": "200000",
  "LastLedgerSequence": 6387604,
  "RedemptionDate": 846218001,
  "Sequence": 6373348,
  "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
  "SubscriptionDate": 846189321,
  "TransactionType": "VaultCreate",
  "TxnSignature": "B45F14CD2A7995B77E75B1DF7B51C1FCF805B1FDF6515D27EB1D8E66082D8E1B18A41669882AF9A8AD5481A1CDA88232C6A964EB843C86612718E8A1C5D12A0C",
  "VaultKind": 1
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "CreatedNode",
      "LedgerEntryType": "MPTokenIssuance",
      "LedgerIndex": "0FB4A9A551ACFB8C21ECCFCEA1BEAB1D1F1E57DA96D0D53D8342F2AC996616D6",
      "fields": {
        "Flags": 56,
        "Issuer": "rNrU3N4h5CyfKQ3SQsMrHBNWd61VBZNo5T",
        "Sequence": 1
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "1322E406E458AAB39AF0282DFAD784A4CC82A4BC276E0C067B4367B45B1A9DD2"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "15A5A87C2BC15DCE3A43CCEBC7C3084C64189C789FF8B5A8CC0AF17870B86D6E"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "MPToken",
      "LedgerIndex": "1D5B8EA49A0A0AF4DFBA3ECB166D1FCC6C3BBA738993B30750A9837E387644F4",
      "fields": {
        "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "MPTokenIssuanceID": "000000018EA2EBED47631F388C34082D16CBCA900BF07116"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "5826001699F236B2365E566973F37F6C92A90CAD35F85D79A5C4B4A90FD48399"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "Vault",
      "LedgerIndex": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
      "fields": {
        "Account": "rNrU3N4h5CyfKQ3SQsMrHBNWd61VBZNo5T",
        "LEVersion": 1,
        "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "RedemptionDate": 846218001,
        "Sequence": 6373348,
        "ShareMPTID": "000000018EA2EBED47631F388C34082D16CBCA900BF07116",
        "SubscriptionDate": 846189321,
        "VaultKind": 1,
        "WithdrawalPolicy": 1
      }
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DC7D92AACB934A9D365F97C3C3186638E4F4BC8424E65AA19D294CF33689E550"
    }
  ]
}
```
### credentialCreate
- hash: [`AA7A0475E55E826C3472085115F51B05254A8C5B46F05DE86CAAE57DBF0A4A5B`](https://devnet.xrpl.org/transactions/AA7A0475E55E826C3472085115F51B05254A8C5B46F05DE86CAAE57DBF0A4A5B)
- validated: `True`, ledger `6387699`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
  "CredentialType": "6B79622D626F72726F776572",
  "Fee": "1",
  "LastLedgerSequence": 6387717,
  "Sequence": 6373352,
  "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
  "Subject": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "TransactionType": "CredentialCreate",
  "TxnSignature": "AB74C40FB43A205249D4F434B48297018340EC3EF3BA143B6C376A0A96E9E4AC8DBDA7C4A795991DDDD9975B5A2D15D8BB00202122C011B18A364F9FB3F6190E"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "1322E406E458AAB39AF0282DFAD784A4CC82A4BC276E0C067B4367B45B1A9DD2"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "Credential",
      "LedgerIndex": "491C76600B21BDD93CD802874BA7ABA6EDB7F90ACCF0D97D29E61BAF96CF47C9"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "5826001699F236B2365E566973F37F6C92A90CAD35F85D79A5C4B4A90FD48399"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "DA72608A1466C9144F0BDE650671300E1DCAECE267B869FF3DBA8F62CAF622CF"
    }
  ]
}
```
### credentialAccept
- hash: [`48B1D7E9918E593833028877E0EF4E7D07DC3E756AE3882C795C3C8D7C110D6A`](https://devnet.xrpl.org/transactions/48B1D7E9918E593833028877E0EF4E7D07DC3E756AE3882C795C3C8D7C110D6A)
- validated: `True`, ledger `6387701`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "CredentialType": "6B79622D626F72726F776572",
  "Fee": "1",
  "Issuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
  "LastLedgerSequence": 6387719,
  "Sequence": 6387693,
  "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
  "TransactionType": "CredentialAccept",
  "TxnSignature": "5715ABD64DB29F7143D4379760CF0461EC5D11E95D81432041B0914C249A73832A4BABDA8626324F7EFCC5C32176BD24C9F761FE778092DDD4336A78BC1B4C04"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "1322E406E458AAB39AF0282DFAD784A4CC82A4BC276E0C067B4367B45B1A9DD2"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "35F1A1A4D4445501C095F280D1F3AFC8649782D25B868BA8AD150A768E143454"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "Credential",
      "LedgerIndex": "491C76600B21BDD93CD802874BA7ABA6EDB7F90ACCF0D97D29E61BAF96CF47C9"
    }
  ]
}
```
### loanBrokerSet
- hash: [`EAC14DCCDC8F5166319B37FB8208D8F3B0C36630D6C3ACB199A031641692A8DA`](https://devnet.xrpl.org/transactions/EAC14DCCDC8F5166319B37FB8208D8F3B0C36630D6C3ACB199A031641692A8DA)
- validated: `True`, ledger `6387588`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
  "CoverRateLiquidation": 100000,
  "CoverRateMinimum": 10000,
  "DebtMaximum": "0",
  "Fee": "1",
  "LastLedgerSequence": 6387606,
  "ManagementFeeRate": 1000,
  "Sequence": 6373349,
  "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
  "TransactionType": "LoanBrokerSet",
  "TxnSignature": "E837E4D2D7A6D54F78338712098E3354C90F6CF8247FF1F8591900E28298530A712D1CB6B5FF71BD7EB45323566DE4B086ACA14B3299B047980BE89D4905AD0A",
  "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "1322E406E458AAB39AF0282DFAD784A4CC82A4BC276E0C067B4367B45B1A9DD2"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "15A5A87C2BC15DCE3A43CCEBC7C3084C64189C789FF8B5A8CC0AF17870B86D6E"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "559A731CF5815377DC1E41FE2E409CBB0294A6ACFE3E6558FBC1DC488E9B1DE3"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "5826001699F236B2365E566973F37F6C92A90CAD35F85D79A5C4B4A90FD48399"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "LoanBroker",
      "LedgerIndex": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
      "fields": {
        "Account": "rDgnwHG2okiJJdbK8sf4eghJY3Wk4sHMka",
        "CoverRateLiquidation": 100000,
        "CoverRateMinimum": 10000,
        "LoanSequence": 1,
        "ManagementFeeRate": 1000,
        "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "Sequence": 6373349,
        "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51"
      }
    }
  ]
}
```
### coverDeposit
- hash: [`321D8224A85C524618B5FC80F6B10C8EED32B25C0EA6612288EA6873E14958C2`](https://devnet.xrpl.org/transactions/321D8224A85C524618B5FC80F6B10C8EED32B25C0EA6612288EA6873E14958C2)
- validated: `True`, ledger `6387703`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
  "Amount": "12666667",
  "Fee": "1",
  "LastLedgerSequence": 6387721,
  "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
  "Sequence": 6373353,
  "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
  "TransactionType": "LoanBrokerCoverDeposit",
  "TxnSignature": "DADC29BD8F20E5E27FA030CD34CE657FD5CAE5715B17D0F2C1671D37C5D12C4D553597E769C3BB93AE9D466C60DD5913379170AB520B66D62061F1BF997D3100"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "1322E406E458AAB39AF0282DFAD784A4CC82A4BC276E0C067B4367B45B1A9DD2"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "559A731CF5815377DC1E41FE2E409CBB0294A6ACFE3E6558FBC1DC488E9B1DE3"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "LoanBroker",
      "LedgerIndex": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
      "fields": {
        "Account": "rDgnwHG2okiJJdbK8sf4eghJY3Wk4sHMka",
        "CoverAvailable": "20000000",
        "CoverRateLiquidation": 100000,
        "CoverRateMinimum": 10000,
        "DebtTotal": "66666668",
        "Flags": 0,
        "LoanSequence": 4,
        "ManagementFeeRate": 1000,
        "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "OwnerCount": 3,
        "OwnerNode": "0",
        "Sequence": 6373349,
        "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
        "VaultNode": "0"
      },
      "PreviousFields": {
        "CoverAvailable": "7333333"
      }
    }
  ]
}
```
### depositA
- hash: [`4CB4E9208993C74CA6CE38F249D5CE27782C0AD7EE5CEE4398F7F8E8B853587E`](https://devnet.xrpl.org/transactions/4CB4E9208993C74CA6CE38F249D5CE27782C0AD7EE5CEE4398F7F8E8B853587E)
- validated: `True`, ledger `6387592`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rKecLpa298P3oLJox7zKb6sTfBa9aG2ZjL",
  "Amount": "20000000",
  "Fee": "1",
  "LastLedgerSequence": 6387610,
  "Sequence": 6373335,
  "SigningPubKey": "ED8106A8131F41C86240CC5B92333194618F7833E1BF0F54335036A8F9920893B7",
  "TransactionType": "VaultDeposit",
  "TxnSignature": "5D9EE7F92B3BEE010D68161E519330726A848EAB63E8C4009563A51B498A67CD16750056EDA5E046D5B1E8F4CE6590B175939AF604FAFDE66C041C7435D93302",
  "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "MPTokenIssuance",
      "LedgerIndex": "0FB4A9A551ACFB8C21ECCFCEA1BEAB1D1F1E57DA96D0D53D8342F2AC996616D6",
      "fields": {
        "Flags": 56,
        "Issuer": "rNrU3N4h5CyfKQ3SQsMrHBNWd61VBZNo5T",
        "OutstandingAmount": "20000000",
        "OwnerNode": "0",
        "Sequence": 1
      },
      "PreviousFields": {
        "OutstandingAmount": "0"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "70FCC8A11293B9B389BC411E7F223D10BF59D48B436BD68A8A2D52B13EA5356B"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "7E2E4AB8F62E692FFD2AD67D8A554921628DA367C2CBE363CD375C3B74BF8BF2"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "Vault",
      "LedgerIndex": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
      "fields": {
        "Account": "rNrU3N4h5CyfKQ3SQsMrHBNWd61VBZNo5T",
        "Asset": {
          "currency": "XRP"
        },
        "AssetsAvailable": "20000000",
        "AssetsTotal": "20000000",
        "Flags": 0,
        "LEVersion": 1,
        "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "OwnerNode": "0",
        "RedemptionDate": 846218001,
        "Sequence": 6373348,
        "ShareMPTID": "000000018EA2EBED47631F388C34082D16CBCA900BF07116",
        "SubscriptionDate": 846189321,
        "VaultKind": 1,
        "WithdrawalPolicy": 1
      }
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "MPToken",
      "LedgerIndex": "B797FAED1194E00315B9942C53EB002EB8D326C84F505EC14F92E909B0440999",
      "fields": {
        "Account": "rKecLpa298P3oLJox7zKb6sTfBa9aG2ZjL",
        "MPTAmount": "20000000",
        "MPTokenIssuanceID": "000000018EA2EBED47631F388C34082D16CBCA900BF07116"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DC7D92AACB934A9D365F97C3C3186638E4F4BC8424E65AA19D294CF33689E550"
    }
  ]
}
```
### depositB
- hash: [`0298992C7F57D1ECB14ED9C45AA842033EF1282E51B40901679583A6CB3C9250`](https://devnet.xrpl.org/transactions/0298992C7F57D1ECB14ED9C45AA842033EF1282E51B40901679583A6CB3C9250)
- validated: `True`, ledger `6387594`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rNqeTV1TD32ZzpFX2zAeWnMtLjfgyujKLW",
  "Amount": "10000000",
  "Fee": "1",
  "LastLedgerSequence": 6387613,
  "Sequence": 6373337,
  "SigningPubKey": "ED556E2920E5764A03FC8EFD3E56D008B4B605D12EFD45469D2EE21708B8796979",
  "TransactionType": "VaultDeposit",
  "TxnSignature": "0F0D6BE605FBAF0CC741C11E40746F868D3AC804479819B2DB127DABFDD41EEA201EA2DC97E38DE79091250B2F2D10071E20963C809EDC695946837D8CBE7B0A",
  "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "CreatedNode",
      "LedgerEntryType": "MPToken",
      "LedgerIndex": "047E7CD7DCD924649080A4487C50142419A93B14A930E90027E8E1E78A723940",
      "fields": {
        "Account": "rNqeTV1TD32ZzpFX2zAeWnMtLjfgyujKLW",
        "MPTAmount": "10000000",
        "MPTokenIssuanceID": "000000018EA2EBED47631F388C34082D16CBCA900BF07116"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "0D02945815D723AD593C1C232DA58FEF00ED2A190300DDE57340412BBEBB8720"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "MPTokenIssuance",
      "LedgerIndex": "0FB4A9A551ACFB8C21ECCFCEA1BEAB1D1F1E57DA96D0D53D8342F2AC996616D6",
      "fields": {
        "Flags": 56,
        "Issuer": "rNrU3N4h5CyfKQ3SQsMrHBNWd61VBZNo5T",
        "OutstandingAmount": "30000000",
        "OwnerNode": "0",
        "Sequence": 1
      },
      "PreviousFields": {
        "OutstandingAmount": "20000000"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "646178CBC73AD25A12344A717D3C71022E65F79708473AF1E1F8C9F322CFBEA5"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "Vault",
      "LedgerIndex": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
      "fields": {
        "Account": "rNrU3N4h5CyfKQ3SQsMrHBNWd61VBZNo5T",
        "Asset": {
          "currency": "XRP"
        },
        "AssetsAvailable": "30000000",
        "AssetsTotal": "30000000",
        "Flags": 0,
        "LEVersion": 1,
        "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "OwnerNode": "0",
        "RedemptionDate": 846218001,
        "Sequence": 6373348,
        "ShareMPTID": "000000018EA2EBED47631F388C34082D16CBCA900BF07116",
        "SubscriptionDate": 846189321,
        "VaultKind": 1,
        "WithdrawalPolicy": 1
      },
      "PreviousFields": {
        "AssetsAvailable": "20000000",
        "AssetsTotal": "20000000"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DC7D92AACB934A9D365F97C3C3186638E4F4BC8424E65AA19D294CF33689E550"
    }
  ]
}
```
## Auto-repay sweeps (data/sweeps.json, verified by the desk)
Each sweep: a customer x402 Payment to the borrower (income), then the borrower's sweeper pays one installment from it with LoanPay (borrower key only). The desk stored the record after reading both hashes on devnet.

### sweep record, loan D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8
```json
{
  "loanId": "D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8",
  "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "loanPayHash": "E276E391D2979A899D85CCDADEC9E48101EB94DA7B9A4E724BC4CEF4A584BF75",
  "incomeHash": "08D4B46C31C611BFC22617EB06BE3F154D3D929BD74D6A4A720A5FCF37A964E9",
  "incomeDrops": "5000000",
  "payer": "rByBccT5CSXGuC1LnxiNtzaXYjGZm3MTq1",
  "drops": "3333335",
  "engineResult": "tesSUCCESS",
  "status": "repaid",
  "ledgerIndex": 6387742,
  "at": 1792874531,
  "verifiedAt": 1792874541
}
```
### sweep income Payment 5 XRP (invoice memo)
- hash: [`08D4B46C31C611BFC22617EB06BE3F154D3D929BD74D6A4A720A5FCF37A964E9`](https://devnet.xrpl.org/transactions/08D4B46C31C611BFC22617EB06BE3F154D3D929BD74D6A4A720A5FCF37A964E9)
- validated: `True`, ledger `6387739`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rByBccT5CSXGuC1LnxiNtzaXYjGZm3MTq1",
  "Amount": "5000000",
  "DeliverMax": "5000000",
  "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "Fee": "1",
  "LastLedgerSequence": 6387757,
  "Memos": [
    {
      "Memo": {
        "MemoData": "7B22696E766F696365223A2022494E562D41522D31373932383734353233222C202264617465223A2022323032362D31302D3234227D",
        "MemoType": "696E766F696365"
      }
    }
  ],
  "Sequence": 6387736,
  "SigningPubKey": "ED9C90D757576CA7277527B5C87498D1875D41D6A76B7EEED9B08E883CFC97F806",
  "TransactionType": "Payment",
  "TxnSignature": "7653E552E9747E24FB8AFC45AF567BC23E42EC8EC0D4F8013BF4F1D9A764A63A52295767DC897A6229DCD9F71BC3A8F36DB1D7BCF6008F7F3A2F925D4431530C"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "35F1A1A4D4445501C095F280D1F3AFC8649782D25B868BA8AD150A768E143454"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "87B8D6B66A2D7BC342627832A8A42AEEFAF5A902F85D4F18803C73003A46FA77"
    }
  ],
  "delivered_amount": "5000000"
}
```
### sweep LoanPay 3.33333 XRP (sweeper, borrower-signed)
- hash: [`E276E391D2979A899D85CCDADEC9E48101EB94DA7B9A4E724BC4CEF4A584BF75`](https://devnet.xrpl.org/transactions/E276E391D2979A899D85CCDADEC9E48101EB94DA7B9A4E724BC4CEF4A584BF75)
- validated: `True`, ledger `6387742`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "Amount": "3333335",
  "Fee": "1",
  "LastLedgerSequence": 6387760,
  "LoanID": "D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8",
  "Sequence": 6387695,
  "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
  "TransactionType": "LoanPay",
  "TxnSignature": "7B32CAB841D100BCD81DB78443ED3C6A7572F7706E3FBEBEBC8CA4C83F2746C0FE2D6CE638520C8E3A14808700EEA6D52254D5457004EC51A2DFC1C131D69B0F"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "35F1A1A4D4445501C095F280D1F3AFC8649782D25B868BA8AD150A768E143454"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "Vault",
      "LedgerIndex": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
      "fields": {
        "Account": "rNrU3N4h5CyfKQ3SQsMrHBNWd61VBZNo5T",
        "Asset": {
          "currency": "XRP"
        },
        "AssetsAvailable": "59333337",
        "AssetsTotal": "132666673",
        "Flags": 0,
        "LEVersion": 1,
        "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "OwnerNode": "0",
        "RedemptionDate": 846218001,
        "Sequence": 6373348,
        "ShareMPTID": "000000018EA2EBED47631F388C34082D16CBCA900BF07116",
        "SubscriptionDate": 846189321,
        "VaultKind": 1,
        "WithdrawalPolicy": 1
      },
      "PreviousFields": {
        "AssetsAvailable": "56000002",
        "AssetsTotal": "132666670"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "Loan",
      "LedgerIndex": "D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8",
      "fields": {
        "Borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
        "Flags": 0,
        "GracePeriod": 60,
        "InterestRate": 8000,
        "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
        "LoanBrokerNode": "0",
        "LoanSequence": 4,
        "NextPaymentDueDate": 846189900,
        "OwnerNode": "0",
        "PaymentInterval": 90,
        "PaymentRemaining": 2,
        "PeriodicPayment": "3333334.855405329915",
        "PreviousPaymentDueDate": 846189810,
        "PrincipalOutstanding": "6666668",
        "StartDate": 846189720,
        "TotalValueOutstanding": "6666670"
      },
      "PreviousFields": {
        "NextPaymentDueDate": 846189810,
        "PaymentRemaining": 3,
        "PrincipalOutstanding": "10000000",
        "TotalValueOutstanding": "10000005"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DC7D92AACB934A9D365F97C3C3186638E4F4BC8424E65AA19D294CF33689E550"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "LoanBroker",
      "LedgerIndex": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
      "fields": {
        "Account": "rDgnwHG2okiJJdbK8sf4eghJY3Wk4sHMka",
        "CoverAvailable": "20000000",
        "CoverRateLiquidation": 100000,
        "CoverRateMinimum": 10000,
        "DebtTotal": "73333336",
        "Flags": 0,
        "LoanSequence": 5,
        "ManagementFeeRate": 1000,
        "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "OwnerCount": 4,
        "OwnerNode": "0",
        "Sequence": 6373349,
        "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
        "VaultNode": "0"
      },
      "PreviousFields": {
        "DebtTotal": "76666668"
      }
    }
  ]
}
```
## Gate-ON device approval, end to end (lr_0030, desk e629fb0)
A held 30 XRP working-capital draw approved on the Ledger: approval Payment `8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C` on testnet (two memos: loan-approval = sha256 of the borrower-signed LoanSet, loan-terms 'approve loan 30 XRP to rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG 6 payments'), verified by the desk (signer, memo hash, terms against the stored blob) before it co-signed. Record: decidedBy ledger.

### gate-ON LoanSet 30 XRP, co-signed after the Ledger approval
- hash: [`C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13`](https://devnet.xrpl.org/transactions/C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13)
- validated: `True`, ledger `6389232`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
  "CounterpartySignature": {
    "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
    "TxnSignature": "B2F8CC15227E17BE724E27B229BEA7024EE83010D4D851B5808483F95FC8A0211EA9772D60099EA1F6E46AE352CFC341F4DB75785EAB6B29F4F9D80F4224FC03"
  },
  "Fee": "30",
  "GracePeriod": 60,
  "InterestRate": 8000,
  "LastLedgerSequence": 6389283,
  "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
  "PaymentInterval": 90,
  "PaymentTotal": 6,
  "PrincipalRequested": "30000000",
  "Sequence": 6387696,
  "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
  "TransactionType": "LoanSet",
  "TxnSignature": "B75691D7ED7B2EEF24F4F869297D40A8646811E8D1410B5DCA7CFB681B3D80511E81112B3E751EF3C56CE8458C992CFC5740F5D98B9F44B0E408BD62D071FC04"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "0F38C76663B6D5310CFA79309E0A00C2A5F26C80C6A9E63B434117FB7066A098"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "35F1A1A4D4445501C095F280D1F3AFC8649782D25B868BA8AD150A768E143454"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "Loan",
      "LedgerIndex": "61AA9DFAE4A68286FBE8D905FDF818D54E59E11D71BDF291DCE777BFCAD430F0",
      "fields": {
        "Borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
        "GracePeriod": 60,
        "InterestRate": 8000,
        "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
        "LoanSequence": 5,
        "NextPaymentDueDate": 846194961,
        "PaymentInterval": 90,
        "PaymentRemaining": 6,
        "PeriodicPayment": "5000003.995438747416",
        "PrincipalOutstanding": "30000000",
        "StartDate": 846194871,
        "TotalValueOutstanding": "30000024"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "Vault",
      "LedgerIndex": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
      "fields": {
        "Account": "rNrU3N4h5CyfKQ3SQsMrHBNWd61VBZNo5T",
        "Asset": {
          "currency": "XRP"
        },
        "AssetsAvailable": "29333337",
        "AssetsTotal": "132666673",
        "Flags": 0,
        "LEVersion": 1,
        "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "OwnerNode": "0",
        "RedemptionDate": 846218001,
        "Sequence": 6373348,
        "ShareMPTID": "000000018EA2EBED47631F388C34082D16CBCA900BF07116",
        "SubscriptionDate": 846189321,
        "VaultKind": 1,
        "WithdrawalPolicy": 1
      },
      "PreviousFields": {
        "AssetsAvailable": "59333337"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "DA72608A1466C9144F0BDE650671300E1DCAECE267B869FF3DBA8F62CAF622CF"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DC7D92AACB934A9D365F97C3C3186638E4F4BC8424E65AA19D294CF33689E550"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "LoanBroker",
      "LedgerIndex": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
      "fields": {
        "Account": "rDgnwHG2okiJJdbK8sf4eghJY3Wk4sHMka",
        "CoverAvailable": "20000000",
        "CoverRateLiquidation": 100000,
        "CoverRateMinimum": 10000,
        "DebtTotal": "103333336",
        "Flags": 0,
        "LoanSequence": 6,
        "ManagementFeeRate": 1000,
        "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "OwnerCount": 5,
        "OwnerNode": "0",
        "Sequence": 6373349,
        "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
        "VaultNode": "0"
      },
      "PreviousFields": {
        "DebtTotal": "73333336",
        "LoanSequence": 5,
        "OwnerCount": 4
      }
    }
  ]
}
```
### gate-ON Batch AllOrNothing: 29 XRP compute supplier + 1 XRP fee
- hash: [`6C506E2B9E7B6027C9BBC80E6A75480A1DF2382346567F0BD98E60A540A29DDB`](https://devnet.xrpl.org/transactions/6C506E2B9E7B6027C9BBC80E6A75480A1DF2382346567F0BD98E60A540A29DDB)
- validated: `True`, ledger `6389234`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "Fee": "4",
  "Flags": 65536,
  "LastLedgerSequence": 6389283,
  "RawTransactions": [
    {
      "RawTransaction": {
        "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
        "Amount": "29000000",
        "Destination": "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai",
        "Fee": "0",
        "Flags": 1073741824,
        "Memos": [
          {
            "Memo": {
              "MemoData": "7B22696E766F696365223A20224750552D434F4D505554452D484F5552532D31222C202264617465223A2022323032362D31302D3234227D",
              "MemoType": "696E766F696365"
            }
          }
        ],
        "Sequence": 6387698,
        "SigningPubKey": "",
        "TransactionType": "Payment"
      }
    },
    {
      "RawTransaction": {
        "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
        "Amount": "1000000",
        "Destination": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "Fee": "0",
        "Flags": 1073741824,
        "Sequence": 6387699,
        "SigningPubKey": "",
        "TransactionType": "Payment"
      }
    }
  ],
  "Sequence": 6387697,
  "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
  "TransactionType": "Batch",
  "TxnSignature": "E4F5E6190CB5AEA18961F62FCEBD88E084B7C43FC5130868985FA3491A8A6FBA4DA714D0D17586149A04E047A521C3A2F7643CE337221EBB7176476D7E740C02"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "35F1A1A4D4445501C095F280D1F3AFC8649782D25B868BA8AD150A768E143454"
    }
  ]
}
```
### gate-ON inner Payment supplier 29 XRP
- hash: [`EB3922C3198E1B7891F12B4323B6B696CE10834D0E17DE66A218AF8119E618FE`](https://devnet.xrpl.org/transactions/EB3922C3198E1B7891F12B4323B6B696CE10834D0E17DE66A218AF8119E618FE)
- validated: `True`, ledger `6389234`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "Amount": "29000000",
  "DeliverMax": "29000000",
  "Destination": "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai",
  "Fee": "0",
  "Flags": 1073741824,
  "Memos": [
    {
      "Memo": {
        "MemoData": "7B22696E766F696365223A20224750552D434F4D505554452D484F5552532D31222C202264617465223A2022323032362D31302D3234227D",
        "MemoType": "696E766F696365"
      }
    }
  ],
  "Sequence": 6387698,
  "SigningPubKey": "",
  "TransactionType": "Payment"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "35F1A1A4D4445501C095F280D1F3AFC8649782D25B868BA8AD150A768E143454"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "6D1CC8EF40B8B948C9BE49192D402956C614BBE5C51FA0DCA9465A3A1337C2A9"
    }
  ],
  "delivered_amount": "29000000"
}
```
### gate-ON inner Payment broker fee 1 XRP
- hash: [`1760EA4403177EF90BEBF8EE1509777E810DD25FCBBB54F71B83E52ABDCE5CD6`](https://devnet.xrpl.org/transactions/1760EA4403177EF90BEBF8EE1509777E810DD25FCBBB54F71B83E52ABDCE5CD6)
- validated: `True`, ledger `6389234`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "Amount": "1000000",
  "DeliverMax": "1000000",
  "Destination": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
  "Fee": "0",
  "Flags": 1073741824,
  "Sequence": 6387699,
  "SigningPubKey": "",
  "TransactionType": "Payment"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "1322E406E458AAB39AF0282DFAD784A4CC82A4BC276E0C067B4367B45B1A9DD2"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "35F1A1A4D4445501C095F280D1F3AFC8649782D25B868BA8AD150A768E143454"
    }
  ],
  "delivered_amount": "1000000"
}
```
## Phase 3 findings (batch spike, drill, cover fix)
### batch spike LoanBrokerSet (liquidation 100000)
- hash: [`3CFEBBBE9CED518A9F1AAA6D0683F22BFF27A705B65977CEFD945A2A33B7B6B6`](https://devnet.xrpl.org/transactions/3CFEBBBE9CED518A9F1AAA6D0683F22BFF27A705B65977CEFD945A2A33B7B6B6)
- validated: `True`, ledger `6378768`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
  "CoverRateLiquidation": 100000,
  "CoverRateMinimum": 10000,
  "DebtMaximum": "0",
  "Fee": "1",
  "LastLedgerSequence": 6378786,
  "ManagementFeeRate": 1000,
  "Sequence": 6378758,
  "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
  "TransactionType": "LoanBrokerSet",
  "TxnSignature": "3BD5BD59103D6A071CCAAEBCA6C71EE4D7A3030291AC0FDCA2CDA667804F39902389A72B983D80135558E87D549409C6187C574AC376AA3D14FD8CFE6EE8E50A",
  "VaultID": "F34E451517F5334CF8951FB29EF1BB08F86CFA4B7D857EEC433AD74A191A4EA4"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "CreatedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "09559976A10E4490FAFEC3A8F280FE1E686F183BB60055BE72279724D4B76B28"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "LoanBroker",
      "LedgerIndex": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
      "fields": {
        "Account": "r4wyB2C11zD8bjHW345mExxsXukokxGe4a",
        "CoverRateLiquidation": 100000,
        "CoverRateMinimum": 10000,
        "LoanSequence": 1,
        "ManagementFeeRate": 1000,
        "Owner": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
        "Sequence": 6378758,
        "VaultID": "F34E451517F5334CF8951FB29EF1BB08F86CFA4B7D857EEC433AD74A191A4EA4"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "25F434F7F81A3AA48F1EFF628E555BD00C1C21BD0DA4721FA8D6729E9A36C33E"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "BE11A466DD530251E9837F514EB998E28EBD547C44BBD9480AA21068F82A643B"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "C57A8B7906A66DC16CBFA9CA29E5C1ACCD24256201328034F687FB89D47FDF26"
    }
  ]
}
```
### batch spike co-signed LoanSet 60 XRP (lands before the Batch)
- hash: [`90B14608F08FD217562606260DB6D8D1AF5E2F4E5882D4876CC28E70C77E1927`](https://devnet.xrpl.org/transactions/90B14608F08FD217562606260DB6D8D1AF5E2F4E5882D4876CC28E70C77E1927)
- validated: `True`, ledger `6378788`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
  "Counterparty": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
  "CounterpartySignature": {
    "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
    "TxnSignature": "60C3E0149E577B683003567426952911004A0393BC33D43E79F23CBBCB4E18788BAEA6DAC178EA222760E25AC9B81B3D9CC3795764B39AB1FC786BE1E1CFCE0D"
  },
  "Fee": "30",
  "GracePeriod": 60,
  "InterestRate": 500,
  "LastLedgerSequence": 6378846,
  "LoanBrokerID": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
  "PaymentInterval": 90,
  "PaymentTotal": 3,
  "PrincipalRequested": "60000000",
  "Sequence": 6378761,
  "SigningPubKey": "EDF9A10127FC51B9F1853EFCA13ACD4D74EA0BB33A292CA4430F7325DE874EE1B6",
  "TransactionType": "LoanSet",
  "TxnSignature": "CF6EA557216905894B5643EF6E63A3330160D99E5702CF5F51C9CF9BB273D989E8E9A309C25C2038EB05CEB00042C3CD2B0B5FBFB1AB2A283AECCA84D5362107"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "LoanBroker",
      "LedgerIndex": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
      "fields": {
        "Account": "r4wyB2C11zD8bjHW345mExxsXukokxGe4a",
        "CoverAvailable": "20000000",
        "CoverRateLiquidation": 100000,
        "CoverRateMinimum": 10000,
        "DebtTotal": "60000000",
        "Flags": 0,
        "LoanSequence": 2,
        "ManagementFeeRate": 1000,
        "Owner": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
        "OwnerCount": 1,
        "OwnerNode": "0",
        "Sequence": 6378758,
        "VaultID": "F34E451517F5334CF8951FB29EF1BB08F86CFA4B7D857EEC433AD74A191A4EA4",
        "VaultNode": "0"
      },
      "PreviousFields": {
        "LoanSequence": 1
      }
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "4A95B99B971002D4CF092E57A89A405B0EF2923FC92E9F5C793A4F759CC83727"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "Loan",
      "LedgerIndex": "6930D229D16AA057B99E9F013943AA386B66FF8780811D1223490563107A24B2",
      "fields": {
        "Borrower": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
        "GracePeriod": 60,
        "InterestRate": 500,
        "LoanBrokerID": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
        "LoanSequence": 1,
        "NextPaymentDueDate": 846161690,
        "PaymentInterval": 90,
        "PaymentRemaining": 3,
        "PeriodicPayment": "20000000.57027638765",
        "PrincipalOutstanding": "60000000",
        "StartDate": 846161600,
        "TotalValueOutstanding": "60000002"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DA949E0C63F0D5E1CB1DA0868BAD4A579033574F5BD35F4B6E3FDEF8BB12D496"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "E7980ECFB3F63A28673CD2AB01E1EA3C913F30640B1E79DF1A737200BFF46A78"
    },
    {
      "node": "CreatedNode",
      "LedgerEntryType": "DirectoryNode",
      "LedgerIndex": "ED133CF6BA9413FAADB451F7B4AD5DDFE39AE6C6BC39D1AC5F5337EFB3D87717"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "Vault",
      "LedgerIndex": "F34E451517F5334CF8951FB29EF1BB08F86CFA4B7D857EEC433AD74A191A4EA4",
      "fields": {
        "Account": "rDiGZ6THGaBLjrE2gsoH3tVkuJqoqq5s9D",
        "Asset": {
          "currency": "XRP"
        },
        "AssetsAvailable": "30000000",
        "AssetsTotal": "90000000",
        "Flags": 0,
        "LEVersion": 1,
        "Owner": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
        "OwnerNode": "0",
        "RedemptionDate": 846190312,
        "Sequence": 6378757,
        "ShareMPTID": "000000018CF2E22CD8131212B3D2BB44FD45FB39403F1EC5",
        "SubscriptionDate": 846161572,
        "VaultKind": 1,
        "WithdrawalPolicy": 1
      },
      "PreviousFields": {
        "AssetsAvailable": "90000000"
      }
    }
  ]
}
```
### batch spike Batch C AllOrNothing: 55 XRP supplier + 1 XRP fee
- hash: [`35DF41124FF1DF972A654BC43A482E087A5322E55E4BDF4549D18D17C0F059FA`](https://devnet.xrpl.org/transactions/35DF41124FF1DF972A654BC43A482E087A5322E55E4BDF4549D18D17C0F059FA)
- validated: `True`, ledger `6378790`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
  "Fee": "4",
  "Flags": 65536,
  "LastLedgerSequence": 6378808,
  "RawTransactions": [
    {
      "RawTransaction": {
        "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
        "Amount": "55000000",
        "Destination": "rnVJbderQvW3HBenZp6j29ELp6noDKau1b",
        "Fee": "0",
        "Flags": 1073741824,
        "Memos": [
          {
            "Memo": {
              "MemoData": "7B22696E766F696365223A2022494E562D42415443482D31222C202264617465223A2022323032362D31302D3234227D",
              "MemoType": "696E766F696365"
            }
          }
        ],
        "Sequence": 6378763,
        "SigningPubKey": "",
        "TransactionType": "Payment"
      }
    },
    {
      "RawTransaction": {
        "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
        "Amount": "1000000",
        "Destination": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
        "Fee": "0",
        "Flags": 1073741824,
        "Sequence": 6378764,
        "SigningPubKey": "",
        "TransactionType": "Payment"
      }
    }
  ],
  "Sequence": 6378762,
  "SigningPubKey": "EDF9A10127FC51B9F1853EFCA13ACD4D74EA0BB33A292CA4430F7325DE874EE1B6",
  "TransactionType": "Batch",
  "TxnSignature": "A8C237105A50BFAD4E2F7BD8725F8D835059B28E614F676B3654D056C1BD1AC860BE4F4486437A23AD5BF76C396B8BBA92CCAB00ED54A1A025D4A626AEC6E70E"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DA949E0C63F0D5E1CB1DA0868BAD4A579033574F5BD35F4B6E3FDEF8BB12D496"
    }
  ]
}
```
### batch spike inner Payment supplier 55 XRP
- hash: [`CEC27BB43A0C353234573F27634F33159EBDE9A469E5F1755625F1CBB2A2397B`](https://devnet.xrpl.org/transactions/CEC27BB43A0C353234573F27634F33159EBDE9A469E5F1755625F1CBB2A2397B)
- validated: `True`, ledger `6378790`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
  "Amount": "55000000",
  "DeliverMax": "55000000",
  "Destination": "rnVJbderQvW3HBenZp6j29ELp6noDKau1b",
  "Fee": "0",
  "Flags": 1073741824,
  "Memos": [
    {
      "Memo": {
        "MemoData": "7B22696E766F696365223A2022494E562D42415443482D31222C202264617465223A2022323032362D31302D3234227D",
        "MemoType": "696E766F696365"
      }
    }
  ],
  "Sequence": 6378763,
  "SigningPubKey": "",
  "TransactionType": "Payment"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "20B3DB6F87D3CBE80CA68111865282AAC953A0919ED736E3770365D84C7D8079"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DA949E0C63F0D5E1CB1DA0868BAD4A579033574F5BD35F4B6E3FDEF8BB12D496"
    }
  ],
  "delivered_amount": "55000000"
}
```
### batch spike inner Payment broker fee 1 XRP
- hash: [`3B49A298F91AF946C002B97BABDA55CB81E7B1240452A43DB7674173B098C6B3`](https://devnet.xrpl.org/transactions/3B49A298F91AF946C002B97BABDA55CB81E7B1240452A43DB7674173B098C6B3)
- validated: `True`, ledger `6378790`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
  "Amount": "1000000",
  "DeliverMax": "1000000",
  "Destination": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
  "Fee": "0",
  "Flags": 1073741824,
  "Sequence": 6378764,
  "SigningPubKey": "",
  "TransactionType": "Payment"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "C57A8B7906A66DC16CBFA9CA29E5C1ACCD24256201328034F687FB89D47FDF26"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DA949E0C63F0D5E1CB1DA0868BAD4A579033574F5BD35F4B6E3FDEF8BB12D496"
    }
  ],
  "delivered_amount": "1000000"
}
```
### batch drill Batch D AllOrNothing, 5000 XRP supplier leg (no inner applies)
- hash: [`2DCCD2D2349A917560F4539AFCCD561D78F5227FC165C257150055B6919A50F5`](https://devnet.xrpl.org/transactions/2DCCD2D2349A917560F4539AFCCD561D78F5227FC165C257150055B6919A50F5)
- validated: `True`, ledger `6378792`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
  "Fee": "4",
  "Flags": 65536,
  "LastLedgerSequence": 6378811,
  "RawTransactions": [
    {
      "RawTransaction": {
        "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
        "Amount": "5000000000",
        "Destination": "rnVJbderQvW3HBenZp6j29ELp6noDKau1b",
        "Fee": "0",
        "Flags": 1073741824,
        "Memos": [
          {
            "Memo": {
              "MemoData": "7B22696E766F696365223A2022494E562D42415443482D32222C202264617465223A2022323032362D31302D3234227D",
              "MemoType": "696E766F696365"
            }
          }
        ],
        "Sequence": 6378766,
        "SigningPubKey": "",
        "TransactionType": "Payment"
      }
    },
    {
      "RawTransaction": {
        "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
        "Amount": "1000000",
        "Destination": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
        "Fee": "0",
        "Flags": 1073741824,
        "Sequence": 6378767,
        "SigningPubKey": "",
        "TransactionType": "Payment"
      }
    }
  ],
  "Sequence": 6378765,
  "SigningPubKey": "EDF9A10127FC51B9F1853EFCA13ACD4D74EA0BB33A292CA4430F7325DE874EE1B6",
  "TransactionType": "Batch",
  "TxnSignature": "6A7F03D28B561BA1C3D45736405FE57856FD43359D787A76984B3F25F713FF97F058F89239889BBFCF94D73E3503CF6B164C16043398C35580BBD84A05A1F50C"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "DA949E0C63F0D5E1CB1DA0868BAD4A579033574F5BD35F4B6E3FDEF8BB12D496"
    }
  ]
}
```
### batch drill inner Payment (not applied)
`6F8FFB50200842336CB82E24761B2B8B1A23A1E11E75862C28243C9B20CDC2CD`: **txnNotFound** Transaction not found.

### cover fix LoanManage default 60 XRP loan (cover 20 -> 14 XRP)
- hash: [`A8DCC89330485B28AA960332DB87D2984C6AB1B2D268B95A80E6B1F628D6991E`](https://devnet.xrpl.org/transactions/A8DCC89330485B28AA960332DB87D2984C6AB1B2D268B95A80E6B1F628D6991E)
- validated: `True`, ledger `6378837`, meta.TransactionResult: **`tesSUCCESS`**

tx_json (as validated on devnet):
```json
{
  "Account": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
  "Fee": "1",
  "Flags": 65536,
  "LastLedgerSequence": 6378855,
  "LoanID": "6930D229D16AA057B99E9F013943AA386B66FF8780811D1223490563107A24B2",
  "Sequence": 6378760,
  "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
  "TransactionType": "LoanManage",
  "TxnSignature": "F93998B8934F6B6F538EFE1E611506FB741E140B2362A27DFD3FB65E31CF7C501D20334BB6EFB2ADFB049DF676C3460C40FBBE57532C721A95A270252CA8710D"
}
```
meta:
```json
{
  "TransactionResult": "tesSUCCESS",
  "AffectedNodes": [
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "09559976A10E4490FAFEC3A8F280FE1E686F183BB60055BE72279724D4B76B28"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "LoanBroker",
      "LedgerIndex": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
      "fields": {
        "Account": "r4wyB2C11zD8bjHW345mExxsXukokxGe4a",
        "CoverAvailable": "14000000",
        "CoverRateLiquidation": 100000,
        "CoverRateMinimum": 10000,
        "Flags": 0,
        "LoanSequence": 2,
        "ManagementFeeRate": 1000,
        "Owner": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
        "OwnerCount": 1,
        "OwnerNode": "0",
        "Sequence": 6378758,
        "VaultID": "F34E451517F5334CF8951FB29EF1BB08F86CFA4B7D857EEC433AD74A191A4EA4",
        "VaultNode": "0"
      },
      "PreviousFields": {
        "CoverAvailable": "20000000",
        "DebtTotal": "60000000"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "Loan",
      "LedgerIndex": "6930D229D16AA057B99E9F013943AA386B66FF8780811D1223490563107A24B2",
      "fields": {
        "Borrower": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
        "Flags": 65536,
        "GracePeriod": 60,
        "InterestRate": 500,
        "LoanBrokerID": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
        "LoanBrokerNode": "0",
        "LoanSequence": 1,
        "OwnerNode": "0",
        "PaymentInterval": 90,
        "PeriodicPayment": "20000000.57027638765",
        "StartDate": 846161600
      },
      "PreviousFields": {
        "Flags": 0,
        "NextPaymentDueDate": 846161690,
        "PaymentRemaining": 3,
        "PrincipalOutstanding": "60000000",
        "TotalValueOutstanding": "60000002"
      }
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "C57A8B7906A66DC16CBFA9CA29E5C1ACCD24256201328034F687FB89D47FDF26"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "AccountRoot",
      "LedgerIndex": "E7980ECFB3F63A28673CD2AB01E1EA3C913F30640B1E79DF1A737200BFF46A78"
    },
    {
      "node": "ModifiedNode",
      "LedgerEntryType": "Vault",
      "LedgerIndex": "F34E451517F5334CF8951FB29EF1BB08F86CFA4B7D857EEC433AD74A191A4EA4",
      "fields": {
        "Account": "rDiGZ6THGaBLjrE2gsoH3tVkuJqoqq5s9D",
        "Asset": {
          "currency": "XRP"
        },
        "AssetsAvailable": "36000000",
        "AssetsTotal": "36000000",
        "Flags": 0,
        "LEVersion": 1,
        "Owner": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
        "OwnerNode": "0",
        "RedemptionDate": 846190312,
        "Sequence": 6378757,
        "ShareMPTID": "000000018CF2E22CD8131212B3D2BB44FD45FB39403F1EC5",
        "SubscriptionDate": 846161572,
        "VaultKind": 1,
        "WithdrawalPolicy": 1
      },
      "PreviousFields": {
        "AssetsAvailable": "30000000",
        "AssetsTotal": "90000000"
      }
    }
  ]
}
```
## Raw submissions, as they happened (data/rawlog.jsonl)
Each entry: the exact JSON we submitted (signed, decoded) and rippled's submit response.

### VaultCreate — 1792874009
```json
{
  "ts": 1792874009,
  "label": "VaultCreate",
  "tx_json": {
    "TransactionType": "VaultCreate",
    "Sequence": 6373348,
    "LastLedgerSequence": 6387604,
    "SubscriptionDate": 846189321,
    "RedemptionDate": 846218001,
    "Fee": "200000",
    "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
    "TxnSignature": "B45F14CD2A7995B77E75B1DF7B51C1FCF805B1FDF6515D27EB1D8E66082D8E1B18A41669882AF9A8AD5481A1CDA88232C6A964EB843C86612718E8A1C5D12A0C",
    "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "VaultKind": 1,
    "Asset": {
      "currency": "XRP"
    }
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "7212DD8BA03EA1201A95562DEC5CCEEE471542F74B6BF98760F0B1002A114313"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387586,
    "created": {
      "MPTokenIssuance": "0FB4A9A551ACFB8C21ECCFCEA1BEAB1D1F1E57DA96D0D53D8342F2AC996616D6",
      "DirectoryNode": "15A5A87C2BC15DCE3A43CCEBC7C3084C64189C789FF8B5A8CC0AF17870B86D6E",
      "MPToken": "1D5B8EA49A0A0AF4DFBA3ECB166D1FCC6C3BBA738993B30750A9837E387644F4",
      "Vault": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
      "AccountRoot": "DC7D92AACB934A9D365F97C3C3186638E4F4BC8424E65AA19D294CF33689E550"
    }
  }
}
```
### LoanBrokerSet — 1792874016
```json
{
  "ts": 1792874016,
  "label": "LoanBrokerSet",
  "tx_json": {
    "TransactionType": "LoanBrokerSet",
    "ManagementFeeRate": 1000,
    "Sequence": 6373349,
    "LastLedgerSequence": 6387606,
    "CoverRateMinimum": 10000,
    "CoverRateLiquidation": 100000,
    "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
    "Fee": "1",
    "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
    "TxnSignature": "E837E4D2D7A6D54F78338712098E3354C90F6CF8247FF1F8591900E28298530A712D1CB6B5FF71BD7EB45323566DE4B086ACA14B3299B047980BE89D4905AD0A",
    "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "DebtMaximum": "0"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "EAC14DCCDC8F5166319B37FB8208D8F3B0C36630D6C3ACB199A031641692A8DA"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387588,
    "created": {
      "AccountRoot": "559A731CF5815377DC1E41FE2E409CBB0294A6ACFE3E6558FBC1DC488E9B1DE3",
      "LoanBroker": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368"
    }
  }
}
```
### LoanBrokerCoverDeposit — 1792874025
```json
{
  "ts": 1792874025,
  "label": "LoanBrokerCoverDeposit",
  "tx_json": {
    "TransactionType": "LoanBrokerCoverDeposit",
    "Sequence": 6373350,
    "LastLedgerSequence": 6387608,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Amount": "20000000",
    "Fee": "1",
    "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
    "TxnSignature": "8E2D6394DFA1C27909F0CC7D7386EA0957177DB644E354A1D8EF095F07E9C338A6667B652941ADFF7C8BDE91E8F12B138B649BC58C584606EDE4F7C4F15FDE03",
    "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "06E2E9F7E239C706818B25A2B1F81BC92CDE9409678F9E4E36A79A519845B901"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387590,
    "created": {}
  }
}
```
### VaultDeposit — 1792874031
```json
{
  "ts": 1792874031,
  "label": "VaultDeposit",
  "tx_json": {
    "TransactionType": "VaultDeposit",
    "Sequence": 6373335,
    "LastLedgerSequence": 6387610,
    "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
    "Amount": "20000000",
    "Fee": "1",
    "SigningPubKey": "ED8106A8131F41C86240CC5B92333194618F7833E1BF0F54335036A8F9920893B7",
    "TxnSignature": "5D9EE7F92B3BEE010D68161E519330726A848EAB63E8C4009563A51B498A67CD16750056EDA5E046D5B1E8F4CE6590B175939AF604FAFDE66C041C7435D93302",
    "Account": "rKecLpa298P3oLJox7zKb6sTfBa9aG2ZjL"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "4CB4E9208993C74CA6CE38F249D5CE27782C0AD7EE5CEE4398F7F8E8B853587E"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387592,
    "created": {
      "MPToken": "B797FAED1194E00315B9942C53EB002EB8D326C84F505EC14F92E909B0440999"
    }
  }
}
```
### VaultDeposit — 1792874038
```json
{
  "ts": 1792874038,
  "label": "VaultDeposit",
  "tx_json": {
    "TransactionType": "VaultDeposit",
    "Sequence": 6373337,
    "LastLedgerSequence": 6387613,
    "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
    "Amount": "10000000",
    "Fee": "1",
    "SigningPubKey": "ED556E2920E5764A03FC8EFD3E56D008B4B605D12EFD45469D2EE21708B8796979",
    "TxnSignature": "0F0D6BE605FBAF0CC741C11E40746F868D3AC804479819B2DB127DABFDD41EEA201EA2DC97E38DE79091250B2F2D10071E20963C809EDC695946837D8CBE7B0A",
    "Account": "rNqeTV1TD32ZzpFX2zAeWnMtLjfgyujKLW"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "0298992C7F57D1ECB14ED9C45AA842033EF1282E51B40901679583A6CB3C9250"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387594,
    "created": {
      "MPToken": "047E7CD7DCD924649080A4487C50142419A93B14A930E90027E8E1E78A723940"
    }
  }
}
```
### VaultDeposit — 1792874052
```json
{
  "ts": 1792874052,
  "label": "VaultDeposit",
  "tx_json": {
    "TransactionType": "VaultDeposit",
    "Sequence": 6373336,
    "LastLedgerSequence": 6387616,
    "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
    "Amount": "100000000",
    "Fee": "1",
    "SigningPubKey": "ED8106A8131F41C86240CC5B92333194618F7833E1BF0F54335036A8F9920893B7",
    "TxnSignature": "77E7D9307EE591E36F2731E1232B3B6394B162810122B1264AA3E561CB330A8116D8CF9961C391CE708696094F404EAFCE8B43FA398EEE6832DB6486D2C5360A",
    "Account": "rKecLpa298P3oLJox7zKb6sTfBa9aG2ZjL"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "8E6C513043D12E1927189478A33BDAE461A3089ECB6C62E1A26AB9C1C6D1C520"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387598,
    "created": {}
  }
}
```
### VaultDeposit — 1792874058
```json
{
  "ts": 1792874058,
  "label": "VaultDeposit",
  "tx_json": {
    "TransactionType": "VaultDeposit",
    "Sequence": 6373338,
    "LastLedgerSequence": 6387618,
    "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
    "Amount": "50000000",
    "Fee": "1",
    "SigningPubKey": "ED556E2920E5764A03FC8EFD3E56D008B4B605D12EFD45469D2EE21708B8796979",
    "TxnSignature": "E87FD0280B331FDA74E3F2F85F80730D8021F206CB6640975F834D576B5D668F258EABEF73713C1DD7E845FB2553DF6CBC92972C28E77D606E15A99AABC8F203",
    "Account": "rNqeTV1TD32ZzpFX2zAeWnMtLjfgyujKLW"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "42CA75B0827369108B93AADFC265FE04ED75DCE724AF1A30B65D9F3BC066E2F0"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387600,
    "created": {}
  }
}
```
### LoanSet step 1/2: borrower-signed blob received by the broker — 1792874133
```json
{
  "ts": 1792874133,
  "label": "LoanSet step 1/2: borrower-signed blob received by the broker",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6385968,
    "LastLedgerSequence": 6387680,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 3,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "EDFFAE02EB6304A201D56A9814161A45C45947B75C071BF8AFC5EBA7EA7391C909",
    "TxnSignature": "9E3A5E8F1CEE5280F0CD8E74ADD273EF1442816F8A859B98235E707167F4912E15841CD61A15F277EDA9A39494A63334FC452BA91E4469FE9D15A03D2FFA2C0C",
    "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "10000000"
  }
}
```
### LoanSet step 2/2: broker adds CounterpartySignature and submits — 1792874142
```json
{
  "ts": 1792874142,
  "label": "LoanSet step 2/2: broker adds CounterpartySignature and submits",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6385968,
    "LastLedgerSequence": 6387680,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 3,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "EDFFAE02EB6304A201D56A9814161A45C45947B75C071BF8AFC5EBA7EA7391C909",
    "TxnSignature": "9E3A5E8F1CEE5280F0CD8E74ADD273EF1442816F8A859B98235E707167F4912E15841CD61A15F277EDA9A39494A63334FC452BA91E4469FE9D15A03D2FFA2C0C",
    "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "10000000",
    "CounterpartySignature": {
      "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
      "TxnSignature": "7848E8C9B063DCADF1E34FB77722EE893BC0CAA38D2EC5834CF71B9A769C542C0218B25F19AECE9D632CDD7968F329DBC5AFCBE31C3AC2B19FF5EBD5D3BF1B02"
    }
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "55A469B2C4CCC33FCFEEE0DB8F067899300246ABB314B5019A25E8E417DDF5BC"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387624,
    "created": {
      "DirectoryNode": "0F38C76663B6D5310CFA79309E0A00C2A5F26C80C6A9E63B434117FB7066A098",
      "Loan": "4F99E62972D556CE84CACB5E45F89DC7AD83FAF6A60EB763FCE2E4CDD0BF2AA9"
    }
  }
}
```
### LoanSet step 1/2: borrower-signed blob received by the broker — 1792874149
```json
{
  "ts": 1792874149,
  "label": "LoanSet step 1/2: borrower-signed blob received by the broker",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6385969,
    "LastLedgerSequence": 6387685,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 3,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "EDFFAE02EB6304A201D56A9814161A45C45947B75C071BF8AFC5EBA7EA7391C909",
    "TxnSignature": "40D65B12BF676753DE347681B1BAAA1891301FBBE4239B6C4E11A1D186D835381FFA607EC6586935A8859CE47EB9916BC8C4594FA029DD88BDFFC1517582EE0A",
    "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "60000000"
  }
}
```
### LoanSet step 2/2: broker adds CounterpartySignature and submits — 1792874154
```json
{
  "ts": 1792874154,
  "label": "LoanSet step 2/2: broker adds CounterpartySignature and submits",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6385969,
    "LastLedgerSequence": 6387685,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 3,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "EDFFAE02EB6304A201D56A9814161A45C45947B75C071BF8AFC5EBA7EA7391C909",
    "TxnSignature": "40D65B12BF676753DE347681B1BAAA1891301FBBE4239B6C4E11A1D186D835381FFA607EC6586935A8859CE47EB9916BC8C4594FA029DD88BDFFC1517582EE0A",
    "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "60000000",
    "CounterpartySignature": {
      "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
      "TxnSignature": "112055D25F743D14CD357F31AA23579C20017CF4AEE6E393E1129833987CF19CC0D33428232BBD5F3DE2651E72834D8F9DB7DFDB887DF63837116D1641F0DF01"
    }
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "3C901B3904C113500390C8E348F51A5CBC305339A521348ABC1F7A83804AFADA"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387628,
    "created": {
      "Loan": "5D87C185A75EA2E40CDFF053533AEFD46ADAB2A2A40DCDC5B9BE8A2733499144"
    }
  }
}
```
### LoanPay — 1792874176
```json
{
  "ts": 1792874176,
  "label": "LoanPay",
  "tx_json": {
    "TransactionType": "LoanPay",
    "Sequence": 6385970,
    "LastLedgerSequence": 6387653,
    "LoanID": "4F99E62972D556CE84CACB5E45F89DC7AD83FAF6A60EB763FCE2E4CDD0BF2AA9",
    "Amount": "3333335",
    "Fee": "1",
    "SigningPubKey": "EDFFAE02EB6304A201D56A9814161A45C45947B75C071BF8AFC5EBA7EA7391C909",
    "TxnSignature": "B8FDEB6AABBFFD5F3B59F751669811AB9A4049CC700BCA441E3BB0C2F9225B89ED00ECD1B9E25EFDF691E40D1F6BB92892A9B82FBB1F15AAF387E78CC7FD0004",
    "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "E734397452AFBF01287DF775095DE7A51609DD2396D20ECC27957BDD44479DED"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387635,
    "created": {}
  }
}
```
### LoanSet step 1/2: borrower-signed blob received by the broker — 1792874192
```json
{
  "ts": 1792874192,
  "label": "LoanSet step 1/2: borrower-signed blob received by the broker",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6385971,
    "LastLedgerSequence": 6387698,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 3,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "EDFFAE02EB6304A201D56A9814161A45C45947B75C071BF8AFC5EBA7EA7391C909",
    "TxnSignature": "8A345F10911CA949AA834965D86517D8354C23093EB569F7E09B1AAC7C4E7BE7F28648BD29BF5B2948918FBCC2FF2C04CC1319ABCFAC5A62F306FD6BD799140A",
    "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "60000000"
  }
}
```
### LoanSet step 2/2: broker adds CounterpartySignature and submits — 1792874197
```json
{
  "ts": 1792874197,
  "label": "LoanSet step 2/2: broker adds CounterpartySignature and submits",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6385971,
    "LastLedgerSequence": 6387698,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 3,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "EDFFAE02EB6304A201D56A9814161A45C45947B75C071BF8AFC5EBA7EA7391C909",
    "TxnSignature": "8A345F10911CA949AA834965D86517D8354C23093EB569F7E09B1AAC7C4E7BE7F28648BD29BF5B2948918FBCC2FF2C04CC1319ABCFAC5A62F306FD6BD799140A",
    "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "60000000",
    "CounterpartySignature": {
      "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
      "TxnSignature": "AFD94A76188C7ABD486DCE15960F6F3F969F0707915EF60D8D7C0EE8E08C4D0B59D64F179C427A1579847CAC50D6139DE5B089878F678D36707AABA99E76DD0E"
    }
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "8557E7008C1068F7840FEDB5386CCB4BD7AFA9FE74C89EB2C7F02EEA3D48D6BA"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387641,
    "created": {
      "Loan": "DFDF6312D4D7F009B28799D2CC8C587EDB5DA696AEFAF21B6D1BD6C67BE59CA3"
    }
  }
}
```
### Working-capital Batch (borrower-signed, tfAllOrNothing) — 1792874203
```json
{
  "ts": 1792874203,
  "label": "Working-capital Batch (borrower-signed, tfAllOrNothing)",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6385972,
    "LastLedgerSequence": 6387698,
    "Fee": "4",
    "SigningPubKey": "EDFFAE02EB6304A201D56A9814161A45C45947B75C071BF8AFC5EBA7EA7391C909",
    "TxnSignature": "02C298A09BF1BCAA45A4E657AA1BE52E1F698E801B2CFAAF221E003B0211471AC7357E13150B32A9A741F69BDF705E5ABBC0BBE9CEA9386EE7DD44921795AF0B",
    "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6385973,
          "Amount": "55000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
          "Destination": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
          "Memos": [
            {
              "Memo": {
                "MemoType": "696E766F696365",
                "MemoData": "7B22696E766F696365223A2022494E562D57432D31373932383734313834222C202264617465223A2022323032362D31302D3234227D"
              }
            }
          ]
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6385974,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
          "Destination": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "CF69AD6ACAEE91600FD54D913D9AB600A7614F57CE99C32AA5B197BF978B6019"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387643,
    "created": {}
  }
}
```
### demo step 9b drill Batch (tfAllOrNothing, supplier leg exceeds the borrower balance) — 1792874219
```json
{
  "ts": 1792874219,
  "label": "demo step 9b drill Batch (tfAllOrNothing, supplier leg exceeds the borrower balance)",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6385975,
    "LastLedgerSequence": 6387666,
    "Fee": "4",
    "SigningPubKey": "EDFFAE02EB6304A201D56A9814161A45C45947B75C071BF8AFC5EBA7EA7391C909",
    "TxnSignature": "7940B208A49B719D44FC049D73A1316C9AF70A992E4B243BF759D1A87533A648810520140373546D2D3E125E79897F491F1B89C6A59B1EDB5CCEA9AF0199700F",
    "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6385976,
          "Amount": "241666569",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
          "Destination": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
          "Memos": [
            {
              "Memo": {
                "MemoType": "696E766F696365",
                "MemoData": "7B22696E766F696365223A2022494E562D57432D313739323837343231332D4452494C4C222C202264617465223A2022323032362D31302D3234227D"
              }
            }
          ]
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6385977,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
          "Destination": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "687B63B5F4F31FA5D884ACEF7F8DE972ADAB9A3DD49B3BA4EAEA12EB2B392533"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387648,
    "created": {}
  }
}
```
### LoanManage — 1792874330
```json
{
  "ts": 1792874330,
  "label": "LoanManage",
  "tx_json": {
    "TransactionType": "LoanManage",
    "Flags": 65536,
    "Sequence": 6373351,
    "LastLedgerSequence": 6387699,
    "LoanID": "5D87C185A75EA2E40CDFF053533AEFD46ADAB2A2A40DCDC5B9BE8A2733499144",
    "Fee": "1",
    "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
    "TxnSignature": "F6503FCF675BDE21634231A07D1659BCCC4BEF0EF8E256132F1DF86AFD8861197C32EDF82C119E704E069EA3ED34FE9EE43CF90EEE54344AA183B5D796CA0005",
    "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "5777AFE33BA266BD8C898492E18C21A22E3FF25119351BB52F15726632785DF8"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387681,
    "created": {}
  }
}
```
### CredentialCreate — 1792874387
```json
{
  "ts": 1792874387,
  "label": "CredentialCreate",
  "tx_json": {
    "TransactionType": "CredentialCreate",
    "Sequence": 6373352,
    "LastLedgerSequence": 6387717,
    "Fee": "1",
    "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
    "TxnSignature": "AB74C40FB43A205249D4F434B48297018340EC3EF3BA143B6C376A0A96E9E4AC8DBDA7C4A795991DDDD9975B5A2D15D8BB00202122C011B18A364F9FB3F6190E",
    "CredentialType": "6B79622D626F72726F776572",
    "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "Subject": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "AA7A0475E55E826C3472085115F51B05254A8C5B46F05DE86CAAE57DBF0A4A5B"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387699,
    "created": {
      "Credential": "491C76600B21BDD93CD802874BA7ABA6EDB7F90ACCF0D97D29E61BAF96CF47C9",
      "DirectoryNode": "DA72608A1466C9144F0BDE650671300E1DCAECE267B869FF3DBA8F62CAF622CF"
    }
  }
}
```
### CredentialAccept — 1792874395
```json
{
  "ts": 1792874395,
  "label": "CredentialAccept",
  "tx_json": {
    "TransactionType": "CredentialAccept",
    "Sequence": 6387693,
    "LastLedgerSequence": 6387719,
    "Fee": "1",
    "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
    "TxnSignature": "5715ABD64DB29F7143D4379760CF0461EC5D11E95D81432041B0914C249A73832A4BABDA8626324F7EFCC5C32176BD24C9F761FE778092DDD4336A78BC1B4C04",
    "CredentialType": "6B79622D626F72726F776572",
    "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Issuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "48B1D7E9918E593833028877E0EF4E7D07DC3E756AE3882C795C3C8D7C110D6A"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387701,
    "created": {}
  }
}
```
### LoanBrokerCoverDeposit — 1792874402
```json
{
  "ts": 1792874402,
  "label": "LoanBrokerCoverDeposit",
  "tx_json": {
    "TransactionType": "LoanBrokerCoverDeposit",
    "Sequence": 6373353,
    "LastLedgerSequence": 6387721,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Amount": "12666667",
    "Fee": "1",
    "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
    "TxnSignature": "DADC29BD8F20E5E27FA030CD34CE657FD5CAE5715B17D0F2C1671D37C5D12C4D553597E769C3BB93AE9D466C60DD5913379170AB520B66D62061F1BF997D3100",
    "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "321D8224A85C524618B5FC80F6B10C8EED32B25C0EA6612288EA6873E14958C2"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387703,
    "created": {}
  }
}
```
### Payment — 1792874417
```json
{
  "ts": 1792874417,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387705,
    "LastLedgerSequence": 6387726,
    "Amount": "3000000",
    "Fee": "1",
    "SigningPubKey": "ED91AE2B8A70E734652F1ABE1688A371C5733B32FA94D4E9D960D26481B909D860",
    "TxnSignature": "19EDE41370F5ACE8EA6746D91FDB99295BAB41EEE04DE6988885536BC1DB5759DCAE5D643B9B23CE794F79BCB9D40BA6E785E613755BC7F4ED7EB10D8813C302",
    "Account": "rE8RjsX4W1gk63kr6friMvTYDGi1mEMSFq",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236303932372D303032222C202264617465223A2022323032362D30392D3237227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "C40A340ECEBCCB9612E424FF6C0D15DF7A90A295B3886F77D5AFF47C90318558"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387707,
    "created": {}
  }
}
```
### Payment — 1792874417
```json
{
  "ts": 1792874417,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387705,
    "LastLedgerSequence": 6387726,
    "Amount": "1000000",
    "Fee": "1",
    "SigningPubKey": "ED85B16EF9C77C9238C7E7AB020C05494668351101E096670ADDF4367F1B498459",
    "TxnSignature": "7D6EBDD5D947BA1FD3287FDC72A00D3610A230270870744E7ED752242BB8CF7309242AA490E3FDF92EA8B9123971FBFDDBE5BBC3751419573DB5C02D7A1D7206",
    "Account": "rDn6n2SCMKNMMjqMZBSTxQdxt89wGDNuTg",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313030312D303035222C202264617465223A2022323032362D31302D3031227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "9516FF95457F478827EB7CC8007C0DB6E8B08837D58E56A2A280DE8FD5249457"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387707,
    "created": {}
  }
}
```
### Payment — 1792874417
```json
{
  "ts": 1792874417,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387705,
    "LastLedgerSequence": 6387726,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "ED62C7CB3747165D613EBA58C82F619DEC12DEFC65D47CCD704F837B15519701A8",
    "TxnSignature": "405E6BBACE7018B0278475F1C5F853BDD40EE855EA44CA2D20D9A4732126DE617587BBD906C3BEEC468846A0383C4EB12614C1D1F61FBC2E2E3AA52C62FA6703",
    "Account": "r32nDoAxX8YVdNzu48oPT5bgXvNMAC5trQ",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236303932392D303033222C202264617465223A2022323032362D30392D3239227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "5E7FDBA34EE9F4B4EF101B55C64B1D785C23A3C810D225D727448F324216E0A0"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387707,
    "created": {}
  }
}
```
### Payment — 1792874417
```json
{
  "ts": 1792874417,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387705,
    "LastLedgerSequence": 6387726,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "EDCD3E79C284340C0B4F278138C7F16EFEE65A0B41F355280635F74370F4A29EBC",
    "TxnSignature": "1DE8D0718262F5218C192A6798DCCA9A8F1F18F206FEA3479EFE27212C46CC4FBC3B260A664992F00F5823BA02B56E7BFB55B90BDD27BD4DF57303620A239903",
    "Account": "rhJHWDJZaXRxJ7dw8RxGQdADNCbHjsrDb6",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236303933302D303034222C202264617465223A2022323032362D30392D3330227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "D60C6E7580ED2CB1D38D52CE4D1295341AEB2919C1AC93BEBC0A72FEC31B406D"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387707,
    "created": {}
  }
}
```
### Payment — 1792874417
```json
{
  "ts": 1792874417,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387705,
    "LastLedgerSequence": 6387726,
    "Amount": "4500000",
    "Fee": "1",
    "SigningPubKey": "ED1F110A894409EDD756F83999AC66E7638E4AFA07F600870BDD09F7053ECF5801",
    "TxnSignature": "82EF90BE4F8D971C46CBD5B0CB2EE830AE9BA99D78BBA87653638EEE27537A8BD09CBF42A8B41CB5B9F35F6BD068BC708F01781284F7E27478E4A9218AD16C08",
    "Account": "rKUKmQ2ZnAQCh24UBDXR89u81SkviJxS4M",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236303932362D303031222C202264617465223A2022323032362D30392D3236227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "8BCBA088A6FFE74F8C43A6832EE6F7C0E5EC61920DDDED4E06C80E1381568302"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387707,
    "created": {}
  }
}
```
### Payment — 1792874423
```json
{
  "ts": 1792874423,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387706,
    "LastLedgerSequence": 6387727,
    "Amount": "3000000",
    "Fee": "1",
    "SigningPubKey": "ED1F110A894409EDD756F83999AC66E7638E4AFA07F600870BDD09F7053ECF5801",
    "TxnSignature": "EE5551F9E7487AE073DC7533A14B4A459F4BAC83ADD2C735C905EC5A462FBF5AE2285E67C4474AFECC4ECBD963CC7B44B32C1A61EDA9BCB3505DFE4297A55803",
    "Account": "rKUKmQ2ZnAQCh24UBDXR89u81SkviJxS4M",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313030322D303036222C202264617465223A2022323032362D31302D3032227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "67CA4D5A2CDF52D9AE29F26363135AF05509CD5BB5EFB00ACB3F85CEBF9A4F8D"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387709,
    "created": {}
  }
}
```
### Payment — 1792874423
```json
{
  "ts": 1792874423,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387706,
    "LastLedgerSequence": 6387727,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "ED85B16EF9C77C9238C7E7AB020C05494668351101E096670ADDF4367F1B498459",
    "TxnSignature": "8CDC2B94AE66271DC494C5C83F1038DA5179750C5A14E48EA6CAEEABB7B7D941B81F49E9C657AC60FAACB6196540B7B267FC864C90F51CDC4994456A162D3D08",
    "Account": "rDn6n2SCMKNMMjqMZBSTxQdxt89wGDNuTg",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313030392D303131222C202264617465223A2022323032362D31302D3039227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "B267F6F2BDF5A5068385448DE109C201017952C09A3AFB648D86A561EB1F9D8C"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387709,
    "created": {}
  }
}
```
### Payment — 1792874424
```json
{
  "ts": 1792874424,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387706,
    "LastLedgerSequence": 6387727,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "ED91AE2B8A70E734652F1ABE1688A371C5733B32FA94D4E9D960D26481B909D860",
    "TxnSignature": "FC63985A7B197B00921407747C55E93A5E324C23F0089936FCD504321B2E0D4B914E5C01F23613E74246E9483175CF85E07D003F766BFD9B5F72A9ED5FE40E08",
    "Account": "rE8RjsX4W1gk63kr6friMvTYDGi1mEMSFq",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313030342D303037222C202264617465223A2022323032362D31302D3034227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "55E9F3D3C6E15B31F5206F933A8645506E4E0CB6748CD751887A458C3F15FA2C"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387709,
    "created": {}
  }
}
```
### Payment — 1792874424
```json
{
  "ts": 1792874424,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387706,
    "LastLedgerSequence": 6387727,
    "Amount": "3500000",
    "Fee": "1",
    "SigningPubKey": "ED62C7CB3747165D613EBA58C82F619DEC12DEFC65D47CCD704F837B15519701A8",
    "TxnSignature": "3DA6D7084060E61EE4133A66DB161EB5015C29E33ADA2DB32057B97BDD6632558E9874DCC96DC7F27153092C78829FD86508B35940D3E6634638D8A03C4BCD03",
    "Account": "r32nDoAxX8YVdNzu48oPT5bgXvNMAC5trQ",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313030352D303038222C202264617465223A2022323032362D31302D3035227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "69D0B4344312C6B1C7EF7678016AA205E13A8F6369B88C231E3763D9904656DB"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387709,
    "created": {}
  }
}
```
### Payment — 1792874424
```json
{
  "ts": 1792874424,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387706,
    "LastLedgerSequence": 6387727,
    "Amount": "3000000",
    "Fee": "1",
    "SigningPubKey": "EDCD3E79C284340C0B4F278138C7F16EFEE65A0B41F355280635F74370F4A29EBC",
    "TxnSignature": "AF74E5FC24C68DB2C0B7918B1C34EE26092A351038DA11250C821F453F48C66723BA06AAD630DF45F1BDE268323E494D0A734E2DDACF7CB78B66F7050E8B1F06",
    "Account": "rhJHWDJZaXRxJ7dw8RxGQdADNCbHjsrDb6",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313030382D303130222C202264617465223A2022323032362D31302D3038227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "0D907E6A6F6BD4CD111DA3F1267D98C79C90E07187057A1CFF04493CAB1EB874"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387709,
    "created": {}
  }
}
```
### Payment — 1792874430
```json
{
  "ts": 1792874430,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387707,
    "LastLedgerSequence": 6387729,
    "Amount": "4000000",
    "Fee": "1",
    "SigningPubKey": "ED91AE2B8A70E734652F1ABE1688A371C5733B32FA94D4E9D960D26481B909D860",
    "TxnSignature": "4997E7E3E2C100D0DA0532AE2799868329E1D600E1821D71D68044993112FD43023F84EDE5E407447C56829C0B2A7367C4D5D7B9CD55281558151E30E7B78508",
    "Account": "rE8RjsX4W1gk63kr6friMvTYDGi1mEMSFq",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313030392D303132222C202264617465223A2022323032362D31302D3039227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "82B3C020DFCAA65F136BEA8A77AEA36E0BE3CC5548A005BE721A843992E812F5"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387711,
    "created": {}
  }
}
```
### Payment — 1792874430
```json
{
  "ts": 1792874430,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387707,
    "LastLedgerSequence": 6387729,
    "Amount": "1000000",
    "Fee": "1",
    "SigningPubKey": "EDCD3E79C284340C0B4F278138C7F16EFEE65A0B41F355280635F74370F4A29EBC",
    "TxnSignature": "2AC2F3F3A3992D8586F247AE15E1D31EE3F3396005D43A174B5FECB280924E0BA008020B6CED9163A1CD522DB79E5B5AAF3956555E1BFA43DAE1D84CCA41B100",
    "Account": "rhJHWDJZaXRxJ7dw8RxGQdADNCbHjsrDb6",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313031332D303135222C202264617465223A2022323032362D31302D3133227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "D91412B4D69C972E728D939A0E6F281DC18734E665C497977414B9C4623DB90B"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387711,
    "created": {}
  }
}
```
### Payment — 1792874430
```json
{
  "ts": 1792874430,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387707,
    "LastLedgerSequence": 6387729,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "ED62C7CB3747165D613EBA58C82F619DEC12DEFC65D47CCD704F837B15519701A8",
    "TxnSignature": "19648061FF2412AD00CC92AF321F5C8CB507FE393BC99E55F3DD608F82CDCB8425F35E13947BCB08711A39C6AC00AADB38E503EC9233795B3D1A27EA1021500B",
    "Account": "r32nDoAxX8YVdNzu48oPT5bgXvNMAC5trQ",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313031302D303133222C202264617465223A2022323032362D31302D3130227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "8B3A4C846FEDC9F6324A6FB02EFA43A00AA09B97172D978DE1E92352ED5CB2D5"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387711,
    "created": {}
  }
}
```
### Payment — 1792874430
```json
{
  "ts": 1792874430,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387707,
    "LastLedgerSequence": 6387729,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "ED85B16EF9C77C9238C7E7AB020C05494668351101E096670ADDF4367F1B498459",
    "TxnSignature": "09F60418F5FBAB761843257A66838C07E83A06A5EABCC11F8DB98FA7BC678654CBADA3AB22442D2D14A86DA98E80A2857349A04F2D8B7ADAE3D575AA49677B03",
    "Account": "rDn6n2SCMKNMMjqMZBSTxQdxt89wGDNuTg",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313031352D303137222C202264617465223A2022323032362D31302D3135227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "083254E28A8854331C9832CA88BB8A98D55B1D169AE4654BFC05C9294575AB60"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387711,
    "created": {}
  }
}
```
### Payment — 1792874430
```json
{
  "ts": 1792874430,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387707,
    "LastLedgerSequence": 6387729,
    "Amount": "2500000",
    "Fee": "1",
    "SigningPubKey": "ED1F110A894409EDD756F83999AC66E7638E4AFA07F600870BDD09F7053ECF5801",
    "TxnSignature": "6D2DB6F021F7C1A9E3AC5BBF3F59616F25B20340FCF4828196827A67F6B0E5D0AE49A02B09D5D2289530D8999A492BEC6717038DB8E434DECC0BAB9325DBA204",
    "Account": "rKUKmQ2ZnAQCh24UBDXR89u81SkviJxS4M",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313030362D303039222C202264617465223A2022323032362D31302D3036227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "402597CD96D37E85EF4712F50F397D36CD1BF22B06C38AB366571C2A5475AC8D"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387711,
    "created": {}
  }
}
```
### Payment — 1792874438
```json
{
  "ts": 1792874438,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387708,
    "LastLedgerSequence": 6387731,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "ED91AE2B8A70E734652F1ABE1688A371C5733B32FA94D4E9D960D26481B909D860",
    "TxnSignature": "FB20F6216A8563EBA689D52D848463D37526FA97A54B60FCFE37F884ADAF2B195A1EE3E1C20E6EAD72C72AA7E0C882A350FDC772220EC5DE14975C019114110D",
    "Account": "rE8RjsX4W1gk63kr6friMvTYDGi1mEMSFq",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313031342D303136222C202264617465223A2022323032362D31302D3134227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "C0365A071FE7BEC4850784AC6E299DCF849CA34506EEFECC9AF981FB4A02EA23"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387713,
    "created": {}
  }
}
```
### Payment — 1792874438
```json
{
  "ts": 1792874438,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387708,
    "LastLedgerSequence": 6387731,
    "Amount": "3000000",
    "Fee": "1",
    "SigningPubKey": "EDCD3E79C284340C0B4F278138C7F16EFEE65A0B41F355280635F74370F4A29EBC",
    "TxnSignature": "1035DBEFE4F9EF275A8502152B5755759B61ABAFF68B953D50ED4BAF51DC9C3C916892A200D2B2829CF4B5E60AD86BE2CB222F249DFA40F26D667FA560D4A706",
    "Account": "rhJHWDJZaXRxJ7dw8RxGQdADNCbHjsrDb6",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313031392D303231222C202264617465223A2022323032362D31302D3139227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "0D44FABF86906DD591957C0E800505EC61B353C8FACD1EF265EC6725F820CCA9"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387713,
    "created": {}
  }
}
```
### Payment — 1792874438
```json
{
  "ts": 1792874438,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387708,
    "LastLedgerSequence": 6387731,
    "Amount": "4000000",
    "Fee": "1",
    "SigningPubKey": "ED1F110A894409EDD756F83999AC66E7638E4AFA07F600870BDD09F7053ECF5801",
    "TxnSignature": "BFBA09BDBFEB91F429BCC4E3D3C0A45ED7718E9F4DE1671056AF93709491B546389FB99305A6E23983F04340D5DE4162E6DBB807544C6DA8638EBF66C0878905",
    "Account": "rKUKmQ2ZnAQCh24UBDXR89u81SkviJxS4M",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313031312D303134222C202264617465223A2022323032362D31302D3131227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "28B15111211083ED415F3C7058CD3FCA838F366007EF2CAF26C8FB456A0F9C79"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387713,
    "created": {}
  }
}
```
### Payment — 1792874438
```json
{
  "ts": 1792874438,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387708,
    "LastLedgerSequence": 6387731,
    "Amount": "2500000",
    "Fee": "1",
    "SigningPubKey": "ED62C7CB3747165D613EBA58C82F619DEC12DEFC65D47CCD704F837B15519701A8",
    "TxnSignature": "5993F107BFE74D51E76F30C0C928E09F8C46A13760703DD12EC1ADCC0EF795F7F54D4B10A2B1B791F0732786FFE8C578E7B757B7F8C84A821F5C236012925406",
    "Account": "r32nDoAxX8YVdNzu48oPT5bgXvNMAC5trQ",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313031372D303138222C202264617465223A2022323032362D31302D3137227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "0E08CEAAC50BDD4727FCDA9F346712D181C2D05B7497CD88A9A4B87F1A5E3CCE"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387713,
    "created": {}
  }
}
```
### Payment — 1792874438
```json
{
  "ts": 1792874438,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387708,
    "LastLedgerSequence": 6387731,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "ED85B16EF9C77C9238C7E7AB020C05494668351101E096670ADDF4367F1B498459",
    "TxnSignature": "B84F45C2DB06A52A3E4273679379A83132538EF0680D3F8230D326959CE27928DC5A757F99B79D6FED670CDA15BC7A1AC690FE640AD16CCFCA8919A0C6A16003",
    "Account": "rDn6n2SCMKNMMjqMZBSTxQdxt89wGDNuTg",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313032322D303233222C202264617465223A2022323032362D31302D3232227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "CF7E7181B894A7E3C1C9B7556024AEB8FDF22FCA854F40903B88A85AB7B65835"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387713,
    "created": {}
  }
}
```
### Payment — 1792874445
```json
{
  "ts": 1792874445,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387709,
    "LastLedgerSequence": 6387733,
    "Amount": "3000000",
    "Fee": "1",
    "SigningPubKey": "ED91AE2B8A70E734652F1ABE1688A371C5733B32FA94D4E9D960D26481B909D860",
    "TxnSignature": "112C05630E94078A5F8727727705A81CEA1FFA7F5F882F832DFEEF957AD4B9A07784B76DD21B42D744B8B409C1B4B6BECE793EA7B7ADD49937EE7C862325AA03",
    "Account": "rE8RjsX4W1gk63kr6friMvTYDGi1mEMSFq",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313031392D303230222C202264617465223A2022323032362D31302D3139227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "50F750CEE98FE84F0FC92DF1A5B66C83DA2CD79C6B20CD6487767923B4AFB594"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387715,
    "created": {}
  }
}
```
### Payment — 1792874446
```json
{
  "ts": 1792874446,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387709,
    "LastLedgerSequence": 6387733,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "ED1F110A894409EDD756F83999AC66E7638E4AFA07F600870BDD09F7053ECF5801",
    "TxnSignature": "5AA7B5232D6E94664FEA672D4C43CFD2121AABF09E06A50C3E3E21ABCFEA0120F3D3BAD3DB466EED576D37BDF782E4BCB56FE10EF690E0DA598A52BC18109F01",
    "Account": "rKUKmQ2ZnAQCh24UBDXR89u81SkviJxS4M",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313031382D303139222C202264617465223A2022323032362D31302D3138227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "48B88C46301DFE752B4AD4A0EAB43F34A6C9DFB60A54787B3997AE5760E80914"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387715,
    "created": {}
  }
}
```
### Payment — 1792874446
```json
{
  "ts": 1792874446,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387709,
    "LastLedgerSequence": 6387733,
    "Amount": "2000000",
    "Fee": "1",
    "SigningPubKey": "ED62C7CB3747165D613EBA58C82F619DEC12DEFC65D47CCD704F837B15519701A8",
    "TxnSignature": "54922CFB42CCF3BF39BB2FF308CD88FFADF0F75FCE24D48042DF74BBD20F4EF053852CB2B24E2D699AA26BD5F3AF7393CD8843B8EA98CD66C0FBFAD8E8AEB506",
    "Account": "r32nDoAxX8YVdNzu48oPT5bgXvNMAC5trQ",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313032302D303232222C202264617465223A2022323032362D31302D3230227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "743E19AA61D2541A1015C98FA0FB0ECCD2FCFC09A459116E8CBB0651FE6D4279"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387715,
    "created": {}
  }
}
```
### Payment — 1792874451
```json
{
  "ts": 1792874451,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387710,
    "LastLedgerSequence": 6387735,
    "Amount": "3000000",
    "Fee": "1",
    "SigningPubKey": "ED1F110A894409EDD756F83999AC66E7638E4AFA07F600870BDD09F7053ECF5801",
    "TxnSignature": "D9245F192F0800947F576868AF0D9170C4C76FB951DA9002B030C7B73AA9437FEF7E13EC2B8E4FF474D3BF072F70146FB37DBEF69DD74746E571FA16419A650F",
    "Account": "rKUKmQ2ZnAQCh24UBDXR89u81SkviJxS4M",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D32303236313032332D303234222C202264617465223A2022323032362D31302D3233227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "778665100D899A6221732682FC403A54CC8F08E09414A11040EC3BA592ED8E3C"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387717,
    "created": {}
  }
}
```
### LoanSet step 1/2: borrower-signed blob received by the broker — 1792874509
```json
{
  "ts": 1792874509,
  "label": "LoanSet step 1/2: borrower-signed blob received by the broker",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6387694,
    "LastLedgerSequence": 6387791,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 3,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
    "TxnSignature": "429D3731E8B6AB7721A66984CDBD3DE7956160F1A873969760312EAC88CAC4042F83DD119A4C69C3D64C6E6E09EAB7AFB554D570A467F55B6A1FD98695F39809",
    "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "10000000"
  }
}
```
### LoanSet step 2/2: broker adds CounterpartySignature and submits — 1792874513
```json
{
  "ts": 1792874513,
  "label": "LoanSet step 2/2: broker adds CounterpartySignature and submits",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6387694,
    "LastLedgerSequence": 6387791,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 3,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
    "TxnSignature": "429D3731E8B6AB7721A66984CDBD3DE7956160F1A873969760312EAC88CAC4042F83DD119A4C69C3D64C6E6E09EAB7AFB554D570A467F55B6A1FD98695F39809",
    "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "10000000",
    "CounterpartySignature": {
      "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
      "TxnSignature": "0340B1A032518A5A6456F7B5ED2444647021C6577717F66BE0A69D8D3E93BB4E0B3A5C9EE08144F6037D08839F58A88F46039FCC6A4EC2D6DD2F32220DFE1C0D"
    }
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "8E68B713EF74480B71D749BAC123480B366A824CCA4569B13757E1F74304D593"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387734,
    "created": {
      "Loan": "D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8"
    }
  }
}
```
### Payment — 1792874530
```json
{
  "ts": 1792874530,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6387736,
    "LastLedgerSequence": 6387757,
    "Amount": "5000000",
    "Fee": "1",
    "SigningPubKey": "ED9C90D757576CA7277527B5C87498D1875D41D6A76B7EEED9B08E883CFC97F806",
    "TxnSignature": "7653E552E9747E24FB8AFC45AF567BC23E42EC8EC0D4F8013BF4F1D9A764A63A52295767DC897A6229DCD9F71BC3A8F36DB1D7BCF6008F7F3A2F925D4431530C",
    "Account": "rByBccT5CSXGuC1LnxiNtzaXYjGZm3MTq1",
    "Destination": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D41522D31373932383734353233222C202264617465223A2022323032362D31302D3234227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "08D4B46C31C611BFC22617EB06BE3F154D3D929BD74D6A4A720A5FCF37A964E9"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387739,
    "created": {}
  }
}
```
### LoanPay — 1792874540
```json
{
  "ts": 1792874540,
  "label": "LoanPay",
  "tx_json": {
    "TransactionType": "LoanPay",
    "Sequence": 6387695,
    "LastLedgerSequence": 6387760,
    "LoanID": "D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8",
    "Amount": "3333335",
    "Fee": "1",
    "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
    "TxnSignature": "7B32CAB841D100BCD81DB78443ED3C6A7572F7706E3FBEBEBC8CA4C83F2746C0FE2D6CE638520C8E3A14808700EEA6D52254D5457004EC51A2DFC1C131D69B0F",
    "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "E276E391D2979A899D85CCDADEC9E48101EB94DA7B9A4E724BC4CEF4A584BF75"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6387742,
    "created": {}
  }
}
```
### Payment — 1792875909
```json
{
  "ts": 1792875909,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6388062,
    "LastLedgerSequence": 6388163,
    "Amount": "5000000",
    "Fee": "1",
    "SigningPubKey": "ED32441911256FBFBE3142CC327D6518AFED1E55FDF610912837AF8CB45787CD3D",
    "TxnSignature": "191EF72A7724104410CB79801C9768BC23A7C3BC914C2D776A7D6CE6E2847A2B599565CB56E9AFCE052CC74C9D6D12C92FEA98DBC5056553BDDCF48F5747520B",
    "Account": "rhGWp96vWezSZkKRQW8qRmn65et9Te5d1f",
    "Destination": "rBvEzCJwLm39v57JE29e4Yi7rszqmfYFZs",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D50472D313739323837353930322D30222C202264617465223A2022323032362D31302D3234227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "7A2D8D1F8A91252C034475723E793C4D5805F7B5F69799BDCC194F2D6C9238F2"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388145,
    "created": {}
  }
}
```
### Payment — 1792875920
```json
{
  "ts": 1792875920,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6388064,
    "LastLedgerSequence": 6388166,
    "Amount": "5000000",
    "Fee": "1",
    "SigningPubKey": "EDDDFE1EA516588645EB79910EC2879EFDFC2502B2615621A27C9D91211BCA63E9",
    "TxnSignature": "59ECB80645957FD43B69C4E58EC0DD6AA3FE700D3F9B2E86707784559BCC7F1CE454ECCEB142EC80BD6771F7B324F38267D61B126C821C6A3A3051F34F9A8B09",
    "Account": "r4GqXAiTBqNWaws9h7eCRK1Cgo59D7BLvc",
    "Destination": "rBvEzCJwLm39v57JE29e4Yi7rszqmfYFZs",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D50472D313739323837353931322D31222C202264617465223A2022323032362D31302D3234227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "921D40581EDC1B5D06808B5EAE17313E84026A84B2D982DFAFC7B0C04AEE7785"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388148,
    "created": {}
  }
}
```
### Payment — 1792875930
```json
{
  "ts": 1792875930,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6388066,
    "LastLedgerSequence": 6388169,
    "Amount": "5000000",
    "Fee": "1",
    "SigningPubKey": "ED715C9A4575401F417F736931CAC08AB4EB1E9D181CD0927BD81E15640DBFD3E2",
    "TxnSignature": "EDD43165BAC30FF248DDF0726E1DB07BCA947A3CD5FDF33036399C4B313AE7945CFD17CF84AD05D96A6C01D5DB69080F0B33EB31C39DD7932E5A84BC3FA2E40A",
    "Account": "rUzPC4Gb1YeYDmDzk9fMrKnbYXx6nEvNZZ",
    "Destination": "rBvEzCJwLm39v57JE29e4Yi7rszqmfYFZs",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D50472D313739323837353932332D32222C202264617465223A2022323032362D31302D3234227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "8F9B4B72461BB4E59D1B13875D1148872E157C2984C4E46370C60CB11CFE50C4"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388151,
    "created": {}
  }
}
```
### Payment — 1792877237
```json
{
  "ts": 1792877237,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6388063,
    "LastLedgerSequence": 6388544,
    "Amount": "5000000",
    "Fee": "1",
    "SigningPubKey": "ED32441911256FBFBE3142CC327D6518AFED1E55FDF610912837AF8CB45787CD3D",
    "TxnSignature": "3BD5C6D0B7893A1C7B83E20FF5F269359599DE8183B26A9AA958447205991AB92AA392922B7C7EAB143CD49C6D538AB1CC810BD685DE631BE6104E67A9855900",
    "Account": "rhGWp96vWezSZkKRQW8qRmn65et9Te5d1f",
    "Destination": "rwNfF12NjdqrPhpmzGGaeKAHWzMfpej4z8",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D50472D313739323837373233312D30222C202264617465223A2022323032362D31302D3234227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "0C1EE5C4F389DD22B0704162302F45088C4CD18D63C7D46C71DE0A1F6C2817C5"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388526,
    "created": {}
  }
}
```
### Payment — 1792877247
```json
{
  "ts": 1792877247,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6388065,
    "LastLedgerSequence": 6388547,
    "Amount": "5000000",
    "Fee": "1",
    "SigningPubKey": "EDDDFE1EA516588645EB79910EC2879EFDFC2502B2615621A27C9D91211BCA63E9",
    "TxnSignature": "74F6E989CC97991A6085FC56081488C2B290D068BA47673B5BD12E094A0EA1B2FD5BA69AFAA5ECA47CFD0CFD57D6D3F6143F95E8766CD0A32237EA422B2A4C0A",
    "Account": "r4GqXAiTBqNWaws9h7eCRK1Cgo59D7BLvc",
    "Destination": "rwNfF12NjdqrPhpmzGGaeKAHWzMfpej4z8",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D50472D313739323837373234322D31222C202264617465223A2022323032362D31302D3234227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "6045F5207DC89696BD254672B8BA6ED2761524BD7E8CE6216FAE7A47859F86B4"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388529,
    "created": {}
  }
}
```
### CredentialCreate — 1792877266
```json
{
  "ts": 1792877266,
  "label": "CredentialCreate",
  "tx_json": {
    "TransactionType": "CredentialCreate",
    "Sequence": 6373354,
    "LastLedgerSequence": 6388552,
    "Fee": "1",
    "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
    "TxnSignature": "4B30AA3DDEB808C9EFAC897D4D63698ABFDD3D9BF51AF2FEAADC1470820D031762BB1463DB186B8B247BF6463A470B799B918A5C5B0B297E487619DFD93AD80B",
    "CredentialType": "6B79622D626F72726F776572",
    "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "Subject": "rwNfF12NjdqrPhpmzGGaeKAHWzMfpej4z8"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "590FD1455CCC76AB872E1BA2CF90282C4D55378A8B95610372C11A0104B20A6E"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388534,
    "created": {
      "Credential": "028167660523D6EE9BB31A678CE45887CBF26F3E6292F4D75BA98915A2E892CE",
      "DirectoryNode": "34ED62715D9DCBDFC4AA6DDFF5CFBF8C28EDE9E6EBF13C4F5EE88AC3B42F2285"
    }
  }
}
```
### CredentialAccept — 1792877272
```json
{
  "ts": 1792877272,
  "label": "CredentialAccept",
  "tx_json": {
    "TransactionType": "CredentialAccept",
    "Sequence": 6388070,
    "LastLedgerSequence": 6388554,
    "Fee": "1",
    "SigningPubKey": "ED131EA8AA8BB842697F36BC0CAE3EAE5A08CBC199CAD3521D7CDAB448DAF80F49",
    "TxnSignature": "065C27DE80FC04B205C2CD59833CDD5409A815B7037F5B9A4974DA1BC3F6F9CB9027D4592874F3CE994FC16A5EC01BF765CB2A5EDEF51AACD801CCC6358FC50F",
    "CredentialType": "6B79622D626F72726F776572",
    "Account": "rwNfF12NjdqrPhpmzGGaeKAHWzMfpej4z8",
    "Issuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "DB80C2631CCB822FAA34C490575F03811281A0713A35F2ABA04433D1DA48B78F"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388536,
    "created": {}
  }
}
```
### Payment — 1792877464
```json
{
  "ts": 1792877464,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6388064,
    "LastLedgerSequence": 6388611,
    "Amount": "5000000",
    "Fee": "1",
    "SigningPubKey": "ED32441911256FBFBE3142CC327D6518AFED1E55FDF610912837AF8CB45787CD3D",
    "TxnSignature": "B50BC5073D10EC6CB5655CE9495C8D38DE17C096FAEEF5C16CA5661DBF752F5A904225D0E1A915D89111228A2E085E31E04BA6348EBFE2EB4FF1877435DA0404",
    "Account": "rhGWp96vWezSZkKRQW8qRmn65et9Te5d1f",
    "Destination": "r3nHvBa1q97LtEYkoQPp2RsSZaSnNQBMNh",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D50472D313739323837373435342D30222C202264617465223A2022323032362D31302D3234227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "D27498271D7CDD6814A988099A115DD6EDC3DE4BEEA7B39C22D6BEAB2EF81792"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388593,
    "created": {}
  }
}
```
### Payment — 1792877473
```json
{
  "ts": 1792877473,
  "label": "Payment",
  "tx_json": {
    "TransactionType": "Payment",
    "Sequence": 6388066,
    "LastLedgerSequence": 6388614,
    "Amount": "5000000",
    "Fee": "1",
    "SigningPubKey": "EDDDFE1EA516588645EB79910EC2879EFDFC2502B2615621A27C9D91211BCA63E9",
    "TxnSignature": "DD67F17ED99080826356623B23A151A18FBAC335FF8A3D83D54499AFEF141CAAC45054EFA22CF2D272A7A8AB105691EA7113EED78E1AA989F9833B503BC12A0D",
    "Account": "r4GqXAiTBqNWaws9h7eCRK1Cgo59D7BLvc",
    "Destination": "r3nHvBa1q97LtEYkoQPp2RsSZaSnNQBMNh",
    "Memos": [
      {
        "Memo": {
          "MemoType": "696E766F696365",
          "MemoData": "7B22696E766F696365223A2022494E562D50472D313739323837373436372D31222C202264617465223A2022323032362D31302D3234227D"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "1D6BC298D8CDF1A69B2CB2D8DEF1AA1093A0C218EF264810F2A94E0EDCE688FD"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388596,
    "created": {}
  }
}
```
### CredentialCreate — 1792877496
```json
{
  "ts": 1792877496,
  "label": "CredentialCreate",
  "tx_json": {
    "TransactionType": "CredentialCreate",
    "Sequence": 6373355,
    "LastLedgerSequence": 6388620,
    "Fee": "1",
    "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
    "TxnSignature": "B53F3E1001DE8F589303A1BC613B64D69112C3D31C29F0424757C42D55B228FF23E0423721A3963841F60D0DAFB1A233578567B91AB7314CA8027A65BA34FF03",
    "CredentialType": "6B79622D626F72726F776572",
    "Account": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "Subject": "r3nHvBa1q97LtEYkoQPp2RsSZaSnNQBMNh"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "D7576539A2EA2B4A73CD38B74291515FE53B3549A815800E0D1FDB1E92663148"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388602,
    "created": {
      "Credential": "D3398E1CFCC91F3FC7563E46F79FDEDEBD3F7CCF33867C7D25594A7C32E5C31F",
      "DirectoryNode": "DCB9DB2E0A7469676202D14F74E0A7DFE2FF43155F0B0E7B957B154F7B579564"
    }
  }
}
```
### CredentialAccept — 1792877501
```json
{
  "ts": 1792877501,
  "label": "CredentialAccept",
  "tx_json": {
    "TransactionType": "CredentialAccept",
    "Sequence": 6388072,
    "LastLedgerSequence": 6388622,
    "Fee": "1",
    "SigningPubKey": "EDDC071C5DB148FDC74DCBA20683553886B14604DC7DB80B6D5517A43124535015",
    "TxnSignature": "858E3D2E59AB1C632D21272EBDB74E9E9ECB7E7D5B7438C31017F9093018DFE5489E69D790356BD53FC2B6173968BA58271FE4E7754046629B9F518F3C47770D",
    "CredentialType": "6B79622D626F72726F776572",
    "Account": "r3nHvBa1q97LtEYkoQPp2RsSZaSnNQBMNh",
    "Issuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "49911420CD5BB86C29E25120B847FDC7BDFBFB54047C7951E0CF7AC766ABFA6C"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6388604,
    "created": {}
  }
}
```
### LoanSet step 1/2: borrower-signed blob received by the broker — 1792879663
```json
{
  "ts": 1792879663,
  "label": "LoanSet step 1/2: borrower-signed blob received by the broker",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6387696,
    "LastLedgerSequence": 6389283,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 6,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
    "TxnSignature": "B75691D7ED7B2EEF24F4F869297D40A8646811E8D1410B5DCA7CFB681B3D80511E81112B3E751EF3C56CE8458C992CFC5740F5D98B9F44B0E408BD62D071FC04",
    "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "30000000"
  }
}
```
### LoanSet step 2/2: broker adds CounterpartySignature and submits — 1792879669
```json
{
  "ts": 1792879669,
  "label": "LoanSet step 2/2: broker adds CounterpartySignature and submits",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6387696,
    "LastLedgerSequence": 6389283,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 6,
    "InterestRate": 8000,
    "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
    "Fee": "30",
    "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
    "TxnSignature": "B75691D7ED7B2EEF24F4F869297D40A8646811E8D1410B5DCA7CFB681B3D80511E81112B3E751EF3C56CE8458C992CFC5740F5D98B9F44B0E408BD62D071FC04",
    "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "Counterparty": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
    "PrincipalRequested": "30000000",
    "CounterpartySignature": {
      "SigningPubKey": "ED7898B9541BF8D21083FE76D4592FFBB2FD807BD0603E76765478F5EDF1B7DF44",
      "TxnSignature": "B2F8CC15227E17BE724E27B229BEA7024EE83010D4D851B5808483F95FC8A0211EA9772D60099EA1F6E46AE352CFC341F4DB75785EAB6B29F4F9D80F4224FC03"
    }
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6389232,
    "created": {
      "Loan": "61AA9DFAE4A68286FBE8D905FDF818D54E59E11D71BDF291DCE777BFCAD430F0"
    }
  }
}
```
### Working-capital Batch (borrower-signed, tfAllOrNothing) — 1792879675
```json
{
  "ts": 1792879675,
  "label": "Working-capital Batch (borrower-signed, tfAllOrNothing)",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6387697,
    "LastLedgerSequence": 6389283,
    "Fee": "4",
    "SigningPubKey": "ED4ECC320BDDC282D42094B81B3D41EFA309B3D06813C8795352B752338D6FBEE2",
    "TxnSignature": "E4F5E6190CB5AEA18961F62FCEBD88E084B7C43FC5130868985FA3491A8A6FBA4DA714D0D17586149A04E047A521C3A2F7643CE337221EBB7176476D7E740C02",
    "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6387698,
          "Amount": "29000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
          "Destination": "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai",
          "Memos": [
            {
              "Memo": {
                "MemoType": "696E766F696365",
                "MemoData": "7B22696E766F696365223A20224750552D434F4D505554452D484F5552532D31222C202264617465223A2022323032362D31302D3234227D"
              }
            }
          ]
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6387699,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
          "Destination": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "6C506E2B9E7B6027C9BBC80E6A75480A1DF2382346567F0BD98E60A540A29DDB"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6389234,
    "created": {}
  }
}
```
## Batch spike, raw submissions (data/batch_rawlog.jsonl, `batch/spike.py`, `batch/probe_inner.py`)
Fresh accounts and a fresh vault, separate from the desk. `temINVALID_INNER_BATCH` is a preflight rejection: rippled does not accept LoanSet (either orientation, with or without CounterpartySignature) or VaultDeposit as a Batch inner transaction. Payments-only Batch after a co-signed LoanSet works.

### VaultCreate — 1792846321
```json
{
  "ts": 1792846321,
  "label": "VaultCreate",
  "tx_json": {
    "TransactionType": "VaultCreate",
    "Sequence": 6378757,
    "LastLedgerSequence": 6378784,
    "SubscriptionDate": 846161572,
    "RedemptionDate": 846190312,
    "Fee": "200000",
    "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
    "TxnSignature": "83E363BAE7DC676DE740B3889AC2BDB6B2DE3EFD3F609E6B70DD53DC5678FAB3FAA725D86794B1C63C169FDA98C9A55EF6B8D6357E561966024F6E6CECC70503",
    "Account": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
    "VaultKind": 1,
    "Asset": {
      "currency": "XRP"
    }
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "878B0AB895A25C888C6ED3AFA3969322EABB5E4543F1EB0EF7663896DE7D2692"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6378766,
    "created": {
      "MPTokenIssuance": "0A87008F4E19F1CDDEB2CFD43EBD7D0E6740B0990DF3B88E4D98553D55E2EA36",
      "DirectoryNode": "BE11A466DD530251E9837F514EB998E28EBD547C44BBD9480AA21068F82A643B",
      "MPToken": "98EA3CD18BE94ABE7499A3416790201E9147643FD83BE31F3C8FF2009B2598C7",
      "AccountRoot": "E7980ECFB3F63A28673CD2AB01E1EA3C913F30640B1E79DF1A737200BFF46A78",
      "Vault": "F34E451517F5334CF8951FB29EF1BB08F86CFA4B7D857EEC433AD74A191A4EA4"
    }
  }
}
```
### LoanBrokerSet — 1792846328
```json
{
  "ts": 1792846328,
  "label": "LoanBrokerSet",
  "tx_json": {
    "TransactionType": "LoanBrokerSet",
    "ManagementFeeRate": 1000,
    "Sequence": 6378758,
    "LastLedgerSequence": 6378786,
    "CoverRateMinimum": 10000,
    "CoverRateLiquidation": 100000,
    "VaultID": "F34E451517F5334CF8951FB29EF1BB08F86CFA4B7D857EEC433AD74A191A4EA4",
    "Fee": "1",
    "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
    "TxnSignature": "3BD5BD59103D6A071CCAAEBCA6C71EE4D7A3030291AC0FDCA2CDA667804F39902389A72B983D80135558E87D549409C6187C574AC376AA3D14FD8CFE6EE8E50A",
    "Account": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
    "DebtMaximum": "0"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "3CFEBBBE9CED518A9F1AAA6D0683F22BFF27A705B65977CEFD945A2A33B7B6B6"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6378768,
    "created": {
      "AccountRoot": "09559976A10E4490FAFEC3A8F280FE1E686F183BB60055BE72279724D4B76B28",
      "LoanBroker": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975"
    }
  }
}
```
### LoanBrokerCoverDeposit — 1792846335
```json
{
  "ts": 1792846335,
  "label": "LoanBrokerCoverDeposit",
  "tx_json": {
    "TransactionType": "LoanBrokerCoverDeposit",
    "Sequence": 6378759,
    "LastLedgerSequence": 6378788,
    "LoanBrokerID": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
    "Amount": "20000000",
    "Fee": "1",
    "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
    "TxnSignature": "119091E72DF50A171A3C99A0858667F254C18499C49F1C7462CE184BD46DA0CE7C458CA58532427944F951A75AFA5B5BAE5EE0AC49667D48E96DCD1F1A9B5002",
    "Account": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "8F8EE1BFEB45EC10A5D2983E913E35B309E0245659B5326FA0016919C5F4EFE2"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6378770,
    "created": {}
  }
}
```
### VaultDeposit — 1792846341
```json
{
  "ts": 1792846341,
  "label": "VaultDeposit",
  "tx_json": {
    "TransactionType": "VaultDeposit",
    "Sequence": 6378759,
    "LastLedgerSequence": 6378790,
    "VaultID": "F34E451517F5334CF8951FB29EF1BB08F86CFA4B7D857EEC433AD74A191A4EA4",
    "Amount": "90000000",
    "Fee": "1",
    "SigningPubKey": "ED70922CCAD23C24C30608AC2D84D9BE2D1A261D224E4A6B0587B43899707C38FC",
    "TxnSignature": "4AE9784751286F1AAE844CDD9632FBF63DC8024D2824595DA2CF78A281FF84ADA400B037050D527E8CBD508B0A5519417BF34D6381507FE98A101B213E8DB802",
    "Account": "rEGx9ohbFHvKyPKTBuHz1abnr3vbVajTb8"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "1CDFF0D4D2496591AA662DC99D4DCF55D1650E0A1B262160BBE0813A6FD21999"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6378772,
    "created": {
      "MPToken": "38FA1CD5F0B1FD38ABF39C973A40143AFF6F0DE511C1C66E9D230623DACDD64C",
      "DirectoryNode": "98264D6C2ECC3360465FE4654FF67C8006FA0333B7518D9B397555FDE9EBBF44"
    }
  }
}
```
### Batch A (LoanSet broker->borrower) — 1792846380
```json
{
  "ts": 1792846380,
  "label": "Batch A (LoanSet broker->borrower)",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6378761,
    "LastLedgerSequence": 6378803,
    "Fee": "7",
    "SigningPubKey": "EDF9A10127FC51B9F1853EFCA13ACD4D74EA0BB33A292CA4430F7325DE874EE1B6",
    "TxnSignature": "C36210B81753EBB83CCDD09EB29647D05FD2F49971527875465A9881A490CECC72CE8633472FC5DEF4CA52CF84C75686D025626A335615186B0CA53F2CC89503",
    "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "LoanSet",
          "Flags": 1073741824,
          "Sequence": 6378760,
          "PaymentInterval": 90,
          "GracePeriod": 60,
          "PaymentTotal": 3,
          "InterestRate": 500,
          "LoanBrokerID": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
          "Counterparty": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "PrincipalRequested": "60000000"
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378762,
          "Amount": "55000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "Destination": "rnVJbderQvW3HBenZp6j29ELp6noDKau1b",
          "Memos": [
            {
              "Memo": {
                "MemoType": "696E766F696365",
                "MemoData": "7B22696E766F696365223A2022494E562D42415443482D31222C202264617465223A2022323032362D31302D3234227D"
              }
            }
          ]
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378763,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "Destination": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH"
        }
      }
    ],
    "BatchSigners": [
      {
        "BatchSigner": {
          "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
          "TxnSignature": "A17A47DCC2E487920A5284A662DF97DD06D312D1B0626C8EDE947DA897E55908C36191845145B751CD4BA70D2DBAEB5A6E48228D53B3EB5EA22DC889E741470B",
          "Account": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "temINVALID_INNER_BATCH",
    "engine_result_code": -250,
    "engine_result_message": "Malformed: Invalid inner batch transaction.",
    "accepted": true,
    "applied": false,
    "hash": "129B829263259230D966336B52664ED9A5CD3E8CA975F9FA047B3AB75678299C"
  }
}
```
### Batch B (LoanSet borrower->broker) — 1792846385
```json
{
  "ts": 1792846385,
  "label": "Batch B (LoanSet borrower->broker)",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6378761,
    "LastLedgerSequence": 6378805,
    "Fee": "7",
    "SigningPubKey": "EDF9A10127FC51B9F1853EFCA13ACD4D74EA0BB33A292CA4430F7325DE874EE1B6",
    "TxnSignature": "D6EA1898CC8DD4459C720514AE39A055394AEF969CA513DC2D61DDD54153F91D05C12D0057DB054BF70C88B781F2EEF328BFC161339BE0CDF9F8A8B0F130A700",
    "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "LoanSet",
          "Flags": 1073741824,
          "Sequence": 6378762,
          "PaymentInterval": 90,
          "GracePeriod": 60,
          "PaymentTotal": 3,
          "InterestRate": 500,
          "LoanBrokerID": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "Counterparty": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
          "PrincipalRequested": "60000000"
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378763,
          "Amount": "55000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "Destination": "rnVJbderQvW3HBenZp6j29ELp6noDKau1b",
          "Memos": [
            {
              "Memo": {
                "MemoType": "696E766F696365",
                "MemoData": "7B22696E766F696365223A2022494E562D42415443482D31222C202264617465223A2022323032362D31302D3234227D"
              }
            }
          ]
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378764,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "Destination": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH"
        }
      }
    ],
    "BatchSigners": [
      {
        "BatchSigner": {
          "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
          "TxnSignature": "81D6EC3CDC0AE6AAB260EA79E12F468A0201D91A152AA0A31B11FC20C1118C6B438689062F6ED62FF9DA9EEADBD26C24C07A24DD51805917430C9082AA684E0E",
          "Account": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "temINVALID_INNER_BATCH",
    "engine_result_code": -250,
    "engine_result_message": "Malformed: Invalid inner batch transaction.",
    "accepted": true,
    "applied": false,
    "hash": "0EBCD3708B398D733439D5EE2507655AA831460753611F4F2BAC7F1883E60709"
  }
}
```
### LoanSet before Batch C — 1792846394
```json
{
  "ts": 1792846394,
  "label": "LoanSet before Batch C",
  "tx_json": {
    "TransactionType": "LoanSet",
    "Sequence": 6378761,
    "LastLedgerSequence": 6378846,
    "PaymentInterval": 90,
    "GracePeriod": 60,
    "PaymentTotal": 3,
    "InterestRate": 500,
    "LoanBrokerID": "14972A74825371AE061CA20D21F2478996DE007EF54033F0326BEF0926B2D975",
    "Fee": "30",
    "SigningPubKey": "EDF9A10127FC51B9F1853EFCA13ACD4D74EA0BB33A292CA4430F7325DE874EE1B6",
    "TxnSignature": "CF6EA557216905894B5643EF6E63A3330160D99E5702CF5F51C9CF9BB273D989E8E9A309C25C2038EB05CEB00042C3CD2B0B5FBFB1AB2A283AECCA84D5362107",
    "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
    "Counterparty": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH",
    "PrincipalRequested": "60000000",
    "CounterpartySignature": {
      "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
      "TxnSignature": "60C3E0149E577B683003567426952911004A0393BC33D43E79F23CBBCB4E18788BAEA6DAC178EA222760E25AC9B81B3D9CC3795764B39AB1FC786BE1E1CFCE0D"
    }
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "90B14608F08FD217562606260DB6D8D1AF5E2F4E5882D4876CC28E70C77E1927"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6378788,
    "created": {
      "DirectoryNode": "ED133CF6BA9413FAADB451F7B4AD5DDFE39AE6C6BC39D1AC5F5337EFB3D87717",
      "Loan": "6930D229D16AA057B99E9F013943AA386B66FF8780811D1223490563107A24B2"
    }
  }
}
```
### Batch C (payments only) — 1792846400
```json
{
  "ts": 1792846400,
  "label": "Batch C (payments only)",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6378762,
    "LastLedgerSequence": 6378808,
    "Fee": "4",
    "SigningPubKey": "EDF9A10127FC51B9F1853EFCA13ACD4D74EA0BB33A292CA4430F7325DE874EE1B6",
    "TxnSignature": "A8C237105A50BFAD4E2F7BD8725F8D835059B28E614F676B3654D056C1BD1AC860BE4F4486437A23AD5BF76C396B8BBA92CCAB00ED54A1A025D4A626AEC6E70E",
    "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378763,
          "Amount": "55000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "Destination": "rnVJbderQvW3HBenZp6j29ELp6noDKau1b",
          "Memos": [
            {
              "Memo": {
                "MemoType": "696E766F696365",
                "MemoData": "7B22696E766F696365223A2022494E562D42415443482D31222C202264617465223A2022323032362D31302D3234227D"
              }
            }
          ]
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378764,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "Destination": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "35DF41124FF1DF972A654BC43A482E087A5322E55E4BDF4549D18D17C0F059FA"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6378790,
    "created": {}
  }
}
```
### Batch D (drill, unpayable) — 1792846408
```json
{
  "ts": 1792846408,
  "label": "Batch D (drill, unpayable)",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6378765,
    "LastLedgerSequence": 6378811,
    "Fee": "4",
    "SigningPubKey": "EDF9A10127FC51B9F1853EFCA13ACD4D74EA0BB33A292CA4430F7325DE874EE1B6",
    "TxnSignature": "6A7F03D28B561BA1C3D45736405FE57856FD43359D787A76984B3F25F713FF97F058F89239889BBFCF94D73E3503CF6B164C16043398C35580BBD84A05A1F50C",
    "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378766,
          "Amount": "5000000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "Destination": "rnVJbderQvW3HBenZp6j29ELp6noDKau1b",
          "Memos": [
            {
              "Memo": {
                "MemoType": "696E766F696365",
                "MemoData": "7B22696E766F696365223A2022494E562D42415443482D32222C202264617465223A2022323032362D31302D3234227D"
              }
            }
          ]
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378767,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "raB6a7BqyfNZRME5ErH6jSysNSNpjVyZow",
          "Destination": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "2DCCD2D2349A917560F4539AFCCD561D78F5227FC165C257150055B6919A50F5"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6378792,
    "created": {}
  }
}
```
### LoanManage — 1792846558
```json
{
  "ts": 1792846558,
  "label": "LoanManage",
  "tx_json": {
    "TransactionType": "LoanManage",
    "Flags": 65536,
    "Sequence": 6378760,
    "LastLedgerSequence": 6378855,
    "LoanID": "6930D229D16AA057B99E9F013943AA386B66FF8780811D1223490563107A24B2",
    "Fee": "1",
    "SigningPubKey": "ED8AB64AB18FDB4FCBBC93EA00CB5E5380439FE2B3DC64AAA98EDD38CE9645FE19",
    "TxnSignature": "F93998B8934F6B6F538EFE1E611506FB741E140B2362A27DFD3FB65E31CF7C501D20334BB6EFB2ADFB049DF676C3460C40FBBE57532C721A95A270252CA8710D",
    "Account": "rsQ9F4CpzmFrYdmpbi4kGBKE7CV1xnHgGH"
  },
  "submit_response": {
    "engine_result": "tesSUCCESS",
    "engine_result_code": 0,
    "engine_result_message": "The transaction was applied. Only final in a validated ledger.",
    "accepted": true,
    "applied": true,
    "hash": "A8DCC89330485B28AA960332DB87D2984C6AB1B2D268B95A80E6B1F628D6991E"
  },
  "final": {
    "validated": true,
    "meta.TransactionResult": "tesSUCCESS",
    "ledgerIndex": 6378837,
    "created": {}
  }
}
```
### probe: LoanSet + CounterpartySignature, broker BatchSigner — 1792846615
```json
{
  "ts": 1792846615,
  "label": "probe: LoanSet + CounterpartySignature, broker BatchSigner",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6378852,
    "LastLedgerSequence": 6378875,
    "Fee": "6",
    "SigningPubKey": "ED085C65CB169A3E5A8EAB5780D31EA4CEBB1C6D5D21CE3E24A0C45522401FC703",
    "TxnSignature": "40C00AED91FE2C85613903BAD784E4392EC7E49A931BB6CD05AB0051AC5A245B3F6864CABD99E846B4EEC7F1086F4D46A9F2F435C5932EAA108AD2373BDBE800",
    "Account": "rGdGcVLJrZeYHPPrDvDhZXyTCxzjzJYWf4",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "LoanSet",
          "Flags": 1073741824,
          "Sequence": 6378853,
          "PaymentInterval": 90,
          "GracePeriod": 60,
          "PaymentTotal": 1,
          "LoanBrokerID": "ABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABAB",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rGdGcVLJrZeYHPPrDvDhZXyTCxzjzJYWf4",
          "Counterparty": "rEGUuTdwj8zwTNGeArJTTz9VUhHJyoTPar",
          "PrincipalRequested": "1000000",
          "CounterpartySignature": {
            "SigningPubKey": "ED915626A534D11FC19AAAA96F108B6962DC994549824D9D62D76F2F678851DD47",
            "TxnSignature": "57A17939C05A662B48B99657C855CB8352CA070772E44B6260C7568FA19D20B4E594C9A82FE46C0EFB27B334A7532D453A6DDBA8BDE1AFA021F016ECCE62D802"
          }
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378853,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rGdGcVLJrZeYHPPrDvDhZXyTCxzjzJYWf4",
          "Destination": "rEGUuTdwj8zwTNGeArJTTz9VUhHJyoTPar"
        }
      }
    ],
    "BatchSigners": [
      {
        "BatchSigner": {
          "SigningPubKey": "ED915626A534D11FC19AAAA96F108B6962DC994549824D9D62D76F2F678851DD47",
          "TxnSignature": "9C4FE19289A5902C98D0DC63F5BEEB862CB1AE4DA51813D70EA8C536BA7FBF8542818627BF68915A932ACF5F4E36AE2CCF72DFF66908EAFB20D582674D658A06",
          "Account": "rEGUuTdwj8zwTNGeArJTTz9VUhHJyoTPar"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "temINVALID_INNER_BATCH",
    "engine_result_code": -250,
    "engine_result_message": "Malformed: Invalid inner batch transaction.",
    "accepted": true,
    "applied": false,
    "hash": "61CB513881ECCFAB6255F545AEEA23F43DF3E665FDF79E83F42D204BEBE75B8E"
  }
}
```
### probe: LoanSet + CounterpartySignature, no BatchSigner — 1792846618
```json
{
  "ts": 1792846618,
  "label": "probe: LoanSet + CounterpartySignature, no BatchSigner",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6378852,
    "LastLedgerSequence": 6378876,
    "Fee": "5",
    "SigningPubKey": "ED085C65CB169A3E5A8EAB5780D31EA4CEBB1C6D5D21CE3E24A0C45522401FC703",
    "TxnSignature": "601CA7E43EE8C86F7EC6CCCADAC4F034F3E00D846C0A6CD0E30B2CE8606EF1F9D250574CF08D380F66160EEA071A17D4AD82435D9C0D1C7D61609517971BAE03",
    "Account": "rGdGcVLJrZeYHPPrDvDhZXyTCxzjzJYWf4",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "LoanSet",
          "Flags": 1073741824,
          "Sequence": 6378853,
          "PaymentInterval": 90,
          "GracePeriod": 60,
          "PaymentTotal": 1,
          "LoanBrokerID": "ABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABAB",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rGdGcVLJrZeYHPPrDvDhZXyTCxzjzJYWf4",
          "Counterparty": "rEGUuTdwj8zwTNGeArJTTz9VUhHJyoTPar",
          "PrincipalRequested": "1000000",
          "CounterpartySignature": {
            "SigningPubKey": "ED915626A534D11FC19AAAA96F108B6962DC994549824D9D62D76F2F678851DD47",
            "TxnSignature": "57A17939C05A662B48B99657C855CB8352CA070772E44B6260C7568FA19D20B4E594C9A82FE46C0EFB27B334A7532D453A6DDBA8BDE1AFA021F016ECCE62D802"
          }
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378853,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rGdGcVLJrZeYHPPrDvDhZXyTCxzjzJYWf4",
          "Destination": "rEGUuTdwj8zwTNGeArJTTz9VUhHJyoTPar"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "temINVALID_INNER_BATCH",
    "engine_result_code": -250,
    "engine_result_message": "Malformed: Invalid inner batch transaction.",
    "accepted": true,
    "applied": false,
    "hash": "9D1656FD245E75D21099B2AE077BF0A0DD0E208C785B2E5B3C91F40194C5704A"
  }
}
```
### probe: LoanSet + CounterpartySignature, broker BatchSigner — 1792846642
```json
{
  "ts": 1792846642,
  "label": "probe: LoanSet + CounterpartySignature, broker BatchSigner",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6378861,
    "LastLedgerSequence": 6378884,
    "Fee": "6",
    "SigningPubKey": "ED556B8F46F0CBFC77A65EC04CE489A34EF37D95BB53A448E3D998C68CD8822457",
    "TxnSignature": "E61D8281442FC6314C54423CD1DF30986512DA026D86683370BA9F378F8E13C4E6D5795046942C2E51305D09581CEC12B39CFD47286229478664C91915D35104",
    "Account": "rwroiNRkoZi2Rwsp76xBEx1zFcuiN6vmQM",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "LoanSet",
          "Flags": 1073741824,
          "Sequence": 6378862,
          "PaymentInterval": 90,
          "GracePeriod": 60,
          "PaymentTotal": 1,
          "LoanBrokerID": "ABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABAB",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rwroiNRkoZi2Rwsp76xBEx1zFcuiN6vmQM",
          "Counterparty": "rHcWbohLQXAyD1QPrag9EnotbjkFgTUiRm",
          "PrincipalRequested": "1000000",
          "CounterpartySignature": {
            "SigningPubKey": "EDD6B46879B85CC4C0BA68464816206553A0FD20578120AEB42B3BA7D3665A491C",
            "TxnSignature": "5373E651B2245ECB344E36050E3A5ABB0D03B4A46D46456C8B9AE3379BABA59CF291AA9659C2025489014533913B65F5E9C01F63A8E41091E1A959C2341D7302"
          }
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378862,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rwroiNRkoZi2Rwsp76xBEx1zFcuiN6vmQM",
          "Destination": "rHcWbohLQXAyD1QPrag9EnotbjkFgTUiRm"
        }
      }
    ],
    "BatchSigners": [
      {
        "BatchSigner": {
          "SigningPubKey": "EDD6B46879B85CC4C0BA68464816206553A0FD20578120AEB42B3BA7D3665A491C",
          "TxnSignature": "B574959798AB62FE4A47502A0790593186B866108C44628C0BA485C407FE6A6B57586B5259585518142F3CBF7E8F817A00660DA171F52D4CC1945F43C0A22603",
          "Account": "rHcWbohLQXAyD1QPrag9EnotbjkFgTUiRm"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "temINVALID_INNER_BATCH",
    "engine_result_code": -250,
    "engine_result_message": "Malformed: Invalid inner batch transaction.",
    "accepted": true,
    "applied": false,
    "hash": "35BB99641DF06C4FB59211EBA3CC745D108B342CC13F08DF4953FF1963556627"
  }
}
```
### probe: LoanSet + CounterpartySignature, no BatchSigner — 1792846644
```json
{
  "ts": 1792846644,
  "label": "probe: LoanSet + CounterpartySignature, no BatchSigner",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6378861,
    "LastLedgerSequence": 6378885,
    "Fee": "5",
    "SigningPubKey": "ED556B8F46F0CBFC77A65EC04CE489A34EF37D95BB53A448E3D998C68CD8822457",
    "TxnSignature": "B7F7F2CF7505101A9836CE193035B615DC22D7F54C86DB79FFA6A4DF49E301D34D5331F4E212F5678CE8DF2528443EE0DEB0BA15687CDC9ABB55D1CFCCFC6D06",
    "Account": "rwroiNRkoZi2Rwsp76xBEx1zFcuiN6vmQM",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "LoanSet",
          "Flags": 1073741824,
          "Sequence": 6378862,
          "PaymentInterval": 90,
          "GracePeriod": 60,
          "PaymentTotal": 1,
          "LoanBrokerID": "ABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABAB",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rwroiNRkoZi2Rwsp76xBEx1zFcuiN6vmQM",
          "Counterparty": "rHcWbohLQXAyD1QPrag9EnotbjkFgTUiRm",
          "PrincipalRequested": "1000000",
          "CounterpartySignature": {
            "SigningPubKey": "EDD6B46879B85CC4C0BA68464816206553A0FD20578120AEB42B3BA7D3665A491C",
            "TxnSignature": "5373E651B2245ECB344E36050E3A5ABB0D03B4A46D46456C8B9AE3379BABA59CF291AA9659C2025489014533913B65F5E9C01F63A8E41091E1A959C2341D7302"
          }
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378862,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rwroiNRkoZi2Rwsp76xBEx1zFcuiN6vmQM",
          "Destination": "rHcWbohLQXAyD1QPrag9EnotbjkFgTUiRm"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "temINVALID_INNER_BATCH",
    "engine_result_code": -250,
    "engine_result_message": "Malformed: Invalid inner batch transaction.",
    "accepted": true,
    "applied": false,
    "hash": "430718E65BA619C0F44DBC34BF9F2A759B5A920FDEE548C97B52F499883682C7"
  }
}
```
### probe: VaultDeposit inner (control) — 1792846647
```json
{
  "ts": 1792846647,
  "label": "probe: VaultDeposit inner (control)",
  "tx_json": {
    "TransactionType": "Batch",
    "Flags": 65536,
    "Sequence": 6378861,
    "LastLedgerSequence": 6378885,
    "Fee": "4",
    "SigningPubKey": "ED556B8F46F0CBFC77A65EC04CE489A34EF37D95BB53A448E3D998C68CD8822457",
    "TxnSignature": "E07A98535F34CBCB7000FA385BB73E8C5D5EA9DD3E5C06F9D6C29A34324C7AF9A8110B0BE7A15ED579DD1DDEF6F0151728900F1BE04B9B67EC9EBDF898B24C02",
    "Account": "rwroiNRkoZi2Rwsp76xBEx1zFcuiN6vmQM",
    "RawTransactions": [
      {
        "RawTransaction": {
          "TransactionType": "VaultDeposit",
          "Flags": 1073741824,
          "Sequence": 6378862,
          "VaultID": "ABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABABAB",
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rwroiNRkoZi2Rwsp76xBEx1zFcuiN6vmQM"
        }
      },
      {
        "RawTransaction": {
          "TransactionType": "Payment",
          "Flags": 1073741824,
          "Sequence": 6378863,
          "Amount": "1000000",
          "Fee": "0",
          "SigningPubKey": "",
          "Account": "rwroiNRkoZi2Rwsp76xBEx1zFcuiN6vmQM",
          "Destination": "rHcWbohLQXAyD1QPrag9EnotbjkFgTUiRm"
        }
      }
    ]
  },
  "submit_response": {
    "engine_result": "temINVALID_INNER_BATCH",
    "engine_result_code": -250,
    "engine_result_message": "Malformed: Invalid inner batch transaction.",
    "accepted": true,
    "applied": false,
    "hash": "46BE45EB7C05F16F1D57C2CC86E0F0EB4B2F2EF18DB909232DD2D802B5164FA6"
  }
}
```
## Ledger objects now
### Vault (ledger 6389252)
```json
{
  "Account": "rNrU3N4h5CyfKQ3SQsMrHBNWd61VBZNo5T",
  "Asset": {
    "currency": "XRP"
  },
  "AssetsAvailable": "29333337",
  "AssetsTotal": "132666673",
  "Flags": 0,
  "LEVersion": 1,
  "LedgerEntryType": "Vault",
  "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
  "OwnerNode": "0",
  "PreviousTxnID": "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13",
  "PreviousTxnLgrSeq": 6389232,
  "RedemptionDate": 846218001,
  "Sequence": 6373348,
  "ShareMPTID": "000000018EA2EBED47631F388C34082D16CBCA900BF07116",
  "SubscriptionDate": 846189321,
  "VaultKind": 1,
  "WithdrawalPolicy": 1,
  "index": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51"
}
```
### LoanBroker (ledger 6389252)
```json
{
  "Account": "rDgnwHG2okiJJdbK8sf4eghJY3Wk4sHMka",
  "CoverAvailable": "20000000",
  "CoverRateLiquidation": 100000,
  "CoverRateMinimum": 10000,
  "DebtTotal": "103333336",
  "Flags": 0,
  "LedgerEntryType": "LoanBroker",
  "LoanSequence": 6,
  "ManagementFeeRate": 1000,
  "Owner": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
  "OwnerCount": 5,
  "OwnerNode": "0",
  "PreviousTxnID": "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13",
  "PreviousTxnLgrSeq": 6389232,
  "Sequence": 6373349,
  "VaultID": "9A7E000ECB71872515FFA54F7C0C92E748D56B5F4E670BB77B5D5893CB7D8A51",
  "VaultNode": "0",
  "index": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368"
}
```
### Loan 4F99E62972D556CE84CACB5E45F89DC7AD83FAF6A60EB763FCE2E4CDD0BF2AA9
```json
{
  "Borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
  "Flags": 0,
  "GracePeriod": 60,
  "InterestRate": 8000,
  "LedgerEntryType": "Loan",
  "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
  "LoanBrokerNode": "0",
  "LoanSequence": 1,
  "NextPaymentDueDate": 846189522,
  "OwnerNode": "0",
  "PaymentInterval": 90,
  "PaymentRemaining": 2,
  "PeriodicPayment": "3333334.855405329915",
  "PreviousPaymentDueDate": 846189432,
  "PreviousTxnID": "E734397452AFBF01287DF775095DE7A51609DD2396D20ECC27957BDD44479DED",
  "PreviousTxnLgrSeq": 6387635,
  "PrincipalOutstanding": "6666668",
  "StartDate": 846189342,
  "TotalValueOutstanding": "6666670",
  "index": "4F99E62972D556CE84CACB5E45F89DC7AD83FAF6A60EB763FCE2E4CDD0BF2AA9"
}
```
### Loan 5D87C185A75EA2E40CDFF053533AEFD46ADAB2A2A40DCDC5B9BE8A2733499144
```json
{
  "Borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
  "Flags": 65536,
  "GracePeriod": 60,
  "InterestRate": 8000,
  "LedgerEntryType": "Loan",
  "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
  "LoanBrokerNode": "0",
  "LoanSequence": 2,
  "OwnerNode": "0",
  "PaymentInterval": 90,
  "PeriodicPayment": "20000009.13243197949",
  "PreviousTxnID": "5777AFE33BA266BD8C898492E18C21A22E3FF25119351BB52F15726632785DF8",
  "PreviousTxnLgrSeq": 6387681,
  "StartDate": 846189360,
  "index": "5D87C185A75EA2E40CDFF053533AEFD46ADAB2A2A40DCDC5B9BE8A2733499144"
}
```
### Loan 61AA9DFAE4A68286FBE8D905FDF818D54E59E11D71BDF291DCE777BFCAD430F0
```json
{
  "Borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "Flags": 0,
  "GracePeriod": 60,
  "InterestRate": 8000,
  "LedgerEntryType": "Loan",
  "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
  "LoanBrokerNode": "0",
  "LoanSequence": 5,
  "NextPaymentDueDate": 846194961,
  "OwnerNode": "0",
  "PaymentInterval": 90,
  "PaymentRemaining": 6,
  "PeriodicPayment": "5000003.995438747416",
  "PreviousTxnID": "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13",
  "PreviousTxnLgrSeq": 6389232,
  "PrincipalOutstanding": "30000000",
  "StartDate": 846194871,
  "TotalValueOutstanding": "30000024",
  "index": "61AA9DFAE4A68286FBE8D905FDF818D54E59E11D71BDF291DCE777BFCAD430F0"
}
```
### Loan D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8
```json
{
  "Borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
  "Flags": 0,
  "GracePeriod": 60,
  "InterestRate": 8000,
  "LedgerEntryType": "Loan",
  "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
  "LoanBrokerNode": "0",
  "LoanSequence": 4,
  "NextPaymentDueDate": 846189900,
  "OwnerNode": "0",
  "PaymentInterval": 90,
  "PaymentRemaining": 2,
  "PeriodicPayment": "3333334.855405329915",
  "PreviousPaymentDueDate": 846189810,
  "PreviousTxnID": "E276E391D2979A899D85CCDADEC9E48101EB94DA7B9A4E724BC4CEF4A584BF75",
  "PreviousTxnLgrSeq": 6387742,
  "PrincipalOutstanding": "6666668",
  "StartDate": 846189720,
  "TotalValueOutstanding": "6666670",
  "index": "D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8"
}
```
### Loan DFDF6312D4D7F009B28799D2CC8C587EDB5DA696AEFAF21B6D1BD6C67BE59CA3
```json
{
  "Borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
  "Flags": 0,
  "GracePeriod": 60,
  "InterestRate": 8000,
  "LedgerEntryType": "Loan",
  "LoanBrokerID": "F2DD425BB210EC95BEB8BC66F239CB761373B4817AECFF0C3127A1C68EA91368",
  "LoanBrokerNode": "0",
  "LoanSequence": 3,
  "NextPaymentDueDate": 846189491,
  "OwnerNode": "0",
  "PaymentInterval": 90,
  "PaymentRemaining": 3,
  "PeriodicPayment": "20000009.13243197949",
  "PreviousTxnID": "8557E7008C1068F7840FEDB5386CCB4BD7AFA9FE74C89EB2C7F02EEA3D48D6BA",
  "PreviousTxnLgrSeq": 6387641,
  "PrincipalOutstanding": "60000000",
  "StartDate": 846189401,
  "TotalValueOutstanding": "60000028",
  "index": "DFDF6312D4D7F009B28799D2CC8C587EDB5DA696AEFAF21B6D1BD6C67BE59CA3"
}
```
## Desk API, real bodies (data/desk_examples.jsonl)
### loan-request auto: POST /v1/loan-requests
```json
{
  "ts": 1792874142,
  "label": "loan-request auto",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "10000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "5000000"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0021",
    "ts": 1792874132,
    "kind": "loan",
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "10000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
      "asOf": 1792874129,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 1653,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 0,
        "loanDebtDrops": "0",
        "loanPrincipalDrops": "0",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "5F093A5F78DBB41EBCEFAC2F1DAD63C1406CA4001A9CBBB5F17D6019CC4D0EBF",
          "5455DB1B49D2B2996C2352B7BDE39E883FF08371D5F55651751982B6EA26EEBF",
          "D28EC92EE4153A5080531429B025161E3984B6B6FAF912992AEEAFD09939202D",
          "E606FD650F5C9E6BE299FEA21ED6C28781E3D236C86C10B9FF6B3B6924F97869",
          "8E1D485B8664038C5E3C6A49CB592382125C33A595C287D81F5A848FC14F843D"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "10000000",
        "termSeconds": 270,
        "existingDebtDrops": "5000000"
      }
    },
    "breakdown": {
      "total": 99,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 100,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 0,
            "points": 10
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 85,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "10000000",
            "points": 40
          },
          {
            "rule": "existingDebtToVolume",
            "value": "5000000",
            "points": 25
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 99,
    "decision": "auto",
    "status": "auto",
    "reason": null,
    "loanId": "4F99E62972D556CE84CACB5E45F89DC7AD83FAF6A60EB763FCE2E4CDD0BF2AA9",
    "txHash": "55A469B2C4CCC33FCFEEE0DB8F067899300246ABB314B5019A25E8E417DDF5BC",
    "engineResult": "tesSUCCESS",
    "decidedBy": "policy",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": 0,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE:6385968",
    "loanSetHash": "A6F01F1FED9F11D1F21129B24635253CE05569C1D0E21C44316960AC8F52A0FC",
    "approvalTxHash": null,
    "notes": []
  }
}
```
### loans: GET /v1/loans
```json
{
  "ts": 1792874144,
  "label": "loans",
  "method": "GET",
  "path": "/v1/loans",
  "request": null,
  "status": 200,
  "response": {
    "loans": [
      {
        "loanId": "4F99E62972D556CE84CACB5E45F89DC7AD83FAF6A60EB763FCE2E4CDD0BF2AA9",
        "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
        "principalDrops": "10000000",
        "totalOutstandingDrops": "10000005",
        "periodicPaymentDrops": "3333335",
        "interestRate": 8000,
        "paymentInterval": 90,
        "gracePeriod": 60,
        "nextPaymentDue": 1792874232,
        "paymentRemaining": 3,
        "startDate": 1792874142,
        "status": "active",
        "requestId": "lr_0021",
        "default": null,
        "sweeps": []
      }
    ],
    "ledgerIndex": 6387625
  }
}
```
### loan-request held: POST /v1/loan-requests
```json
{
  "ts": 1792874148,
  "label": "loan-request held",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "15000000"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0022",
    "ts": 1792874148,
    "kind": "loan",
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
      "asOf": 1792874145,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 1658,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 1,
        "loanDebtDrops": "10000005",
        "loanPrincipalDrops": "10000000",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "5F093A5F78DBB41EBCEFAC2F1DAD63C1406CA4001A9CBBB5F17D6019CC4D0EBF",
          "5455DB1B49D2B2996C2352B7BDE39E883FF08371D5F55651751982B6EA26EEBF",
          "D28EC92EE4153A5080531429B025161E3984B6B6FAF912992AEEAFD09939202D",
          "E606FD650F5C9E6BE299FEA21ED6C28781E3D236C86C10B9FF6B3B6924F97869",
          "8E1D485B8664038C5E3C6A49CB592382125C33A595C287D81F5A848FC14F843D"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "60000000",
        "termSeconds": 270,
        "existingDebtDrops": "15000000"
      }
    },
    "breakdown": {
      "total": 88,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 90,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 1,
            "points": 0
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 70,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "60000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "15000000",
            "points": 25
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 88,
    "decision": "hold",
    "status": "held",
    "reason": "over_auto_limit",
    "loanId": null,
    "txHash": null,
    "engineResult": null,
    "decidedBy": "policy",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": 0,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE:6385969",
    "loanSetHash": "84BB93F20BFB29E3E0840FEC6811FFC09E613AD2FA4312CFBC76645BF2D64A94",
    "approvalTxHash": null,
    "notes": []
  }
}
```
### approve approved: POST /v1/loan-requests/lr_0022/approve
```json
{
  "ts": 1792874154,
  "label": "approve approved",
  "method": "POST",
  "path": "/v1/loan-requests/lr_0022/approve",
  "request": {},
  "status": 200,
  "response": {
    "id": "lr_0022",
    "ts": 1792874148,
    "kind": "loan",
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
      "asOf": 1792874145,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 1658,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 1,
        "loanDebtDrops": "10000005",
        "loanPrincipalDrops": "10000000",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "5F093A5F78DBB41EBCEFAC2F1DAD63C1406CA4001A9CBBB5F17D6019CC4D0EBF",
          "5455DB1B49D2B2996C2352B7BDE39E883FF08371D5F55651751982B6EA26EEBF",
          "D28EC92EE4153A5080531429B025161E3984B6B6FAF912992AEEAFD09939202D",
          "E606FD650F5C9E6BE299FEA21ED6C28781E3D236C86C10B9FF6B3B6924F97869",
          "8E1D485B8664038C5E3C6A49CB592382125C33A595C287D81F5A848FC14F843D"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "60000000",
        "termSeconds": 270,
        "existingDebtDrops": "15000000"
      }
    },
    "breakdown": {
      "total": 88,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 90,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 1,
            "points": 0
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 70,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "60000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "15000000",
            "points": 25
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 88,
    "decision": "hold",
    "status": "approved",
    "reason": "over_auto_limit",
    "loanId": "5D87C185A75EA2E40CDFF053533AEFD46ADAB2A2A40DCDC5B9BE8A2733499144",
    "txHash": "3C901B3904C113500390C8E348F51A5CBC305339A521348ABC1F7A83804AFADA",
    "engineResult": "tesSUCCESS",
    "decidedBy": "human",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": 0,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE:6385969",
    "loanSetHash": "84BB93F20BFB29E3E0840FEC6811FFC09E613AD2FA4312CFBC76645BF2D64A94",
    "approvalTxHash": null,
    "notes": []
  }
}
```
### loan-request refused: POST /v1/loan-requests
```json
{
  "ts": 1792874165,
  "label": "loan-request refused",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "r49cGgGzbMMFQGRuGBxmArBu2xPUhvNicY",
    "principalDrops": "10000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "30000000"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0023",
    "ts": 1792874165,
    "kind": "loan",
    "borrower": "r49cGgGzbMMFQGRuGBxmArBu2xPUhvNicY",
    "principalDrops": "10000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "r49cGgGzbMMFQGRuGBxmArBu2xPUhvNicY",
      "asOf": 1792874162,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 1,
        "inboundPaymentCount": 0,
        "inboundVolumeDrops": "0",
        "distinctPayers": 0,
        "topPayerSharePct": 0.0,
        "activeDays": 0,
        "activeLoans": 0,
        "loanDebtDrops": "0",
        "loanPrincipalDrops": "0",
        "pastDefaults": 0,
        "hasAcceptedCredential": false,
        "sampleTxHashes": [],
        "memoDatedPayments": 0,
        "ledgerActiveDays": 0,
        "x402IncomeDrops": "0",
        "x402Payments": 0,
        "x402Payers": 0,
        "otherInboundDrops": "0"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "10000000",
        "termSeconds": 270,
        "existingDebtDrops": "30000000"
      }
    },
    "breakdown": {
      "total": 20,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 20,
        "rules": [
          {
            "rule": "activeDays",
            "value": 0,
            "points": 0
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "0",
            "points": 0
          },
          {
            "rule": "distinctPayers",
            "value": 0,
            "points": 0
          },
          {
            "rule": "topPayerSharePct",
            "value": 0.0,
            "points": 0
          },
          {
            "rule": "activeLoans",
            "value": 0,
            "points": 10
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": false,
            "points": 0
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 20,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "10000000",
            "points": 0
          },
          {
            "rule": "existingDebtToVolume",
            "value": "30000000",
            "points": 0
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 20,
    "decision": "refuse",
    "status": "refused",
    "reason": "score_too_low",
    "loanId": null,
    "txHash": null,
    "engineResult": null,
    "decidedBy": "policy",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": null,
    "policyHash": "c18f11634a06502a",
    "blobKey": "r49cGgGzbMMFQGRuGBxmArBu2xPUhvNicY:6387630",
    "loanSetHash": "BE3BEEC14320E5956D99379467B3CA31B59D236AC2B88E46A4ED681E112DE67F",
    "approvalTxHash": null,
    "notes": []
  }
}
```
### working-capital held: POST /v1/loan-requests
```json
{
  "ts": 1792874191,
  "label": "working-capital held",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "70000000"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>",
    "disbursement": {
      "supplier": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
      "supplierDrops": "55000000",
      "feeDrops": "1000000",
      "invoice": "INV-WC-1792874184"
    },
    "signedBatch": "<borrower-signed Batch blob, 766 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0024",
    "ts": 1792874191,
    "kind": "working_capital",
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
      "asOf": 1792874187,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 1671,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 2,
        "loanDebtDrops": "66666698",
        "loanPrincipalDrops": "66666668",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "5F093A5F78DBB41EBCEFAC2F1DAD63C1406CA4001A9CBBB5F17D6019CC4D0EBF",
          "5455DB1B49D2B2996C2352B7BDE39E883FF08371D5F55651751982B6EA26EEBF",
          "D28EC92EE4153A5080531429B025161E3984B6B6FAF912992AEEAFD09939202D",
          "E606FD650F5C9E6BE299FEA21ED6C28781E3D236C86C10B9FF6B3B6924F97869",
          "8E1D485B8664038C5E3C6A49CB592382125C33A595C287D81F5A848FC14F843D"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "60000000",
        "termSeconds": 270,
        "existingDebtDrops": "70000000"
      }
    },
    "breakdown": {
      "total": 86,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 90,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 2,
            "points": 0
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 45,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "60000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "70000000",
            "points": 0
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 86,
    "decision": "hold",
    "status": "held",
    "reason": "over_auto_limit",
    "loanId": null,
    "txHash": null,
    "engineResult": null,
    "decidedBy": "policy",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": 1,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE:6385971",
    "loanSetHash": "717E7A85579F0E508764D4F8A7939C692F8CEA557E43856A78FAB0125F5165BB",
    "approvalTxHash": null,
    "batch": {
      "supplier": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
      "supplierDrops": "55000000",
      "feeDrops": "1000000",
      "invoice": "INV-WC-1792874184",
      "hash": null,
      "engineResult": null,
      "legs": []
    },
    "notes": []
  }
}
```
### working-capital approve approved: POST /v1/loan-requests/lr_0024/approve
```json
{
  "ts": 1792874204,
  "label": "working-capital approve approved",
  "method": "POST",
  "path": "/v1/loan-requests/lr_0024/approve",
  "request": {},
  "status": 200,
  "response": {
    "id": "lr_0024",
    "ts": 1792874191,
    "kind": "working_capital",
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
      "asOf": 1792874187,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 1671,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 2,
        "loanDebtDrops": "66666698",
        "loanPrincipalDrops": "66666668",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "5F093A5F78DBB41EBCEFAC2F1DAD63C1406CA4001A9CBBB5F17D6019CC4D0EBF",
          "5455DB1B49D2B2996C2352B7BDE39E883FF08371D5F55651751982B6EA26EEBF",
          "D28EC92EE4153A5080531429B025161E3984B6B6FAF912992AEEAFD09939202D",
          "E606FD650F5C9E6BE299FEA21ED6C28781E3D236C86C10B9FF6B3B6924F97869",
          "8E1D485B8664038C5E3C6A49CB592382125C33A595C287D81F5A848FC14F843D"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "60000000",
        "termSeconds": 270,
        "existingDebtDrops": "70000000"
      }
    },
    "breakdown": {
      "total": 86,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 90,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 2,
            "points": 0
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 45,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "60000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "70000000",
            "points": 0
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 86,
    "decision": "hold",
    "status": "approved",
    "reason": "over_auto_limit",
    "loanId": "DFDF6312D4D7F009B28799D2CC8C587EDB5DA696AEFAF21B6D1BD6C67BE59CA3",
    "txHash": "8557E7008C1068F7840FEDB5386CCB4BD7AFA9FE74C89EB2C7F02EEA3D48D6BA",
    "engineResult": "tesSUCCESS",
    "decidedBy": "human",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": 1,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE:6385971",
    "loanSetHash": "717E7A85579F0E508764D4F8A7939C692F8CEA557E43856A78FAB0125F5165BB",
    "approvalTxHash": null,
    "batch": {
      "supplier": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
      "supplierDrops": "55000000",
      "feeDrops": "1000000",
      "invoice": "INV-WC-1792874184",
      "hash": "CF69AD6ACAEE91600FD54D913D9AB600A7614F57CE99C32AA5B197BF978B6019",
      "engineResult": "tesSUCCESS",
      "legs": [
        {
          "index": 0,
          "type": "Payment",
          "account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
          "destination": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
          "amountDrops": "55000000",
          "hash": "3A5FB051A3020C606140EF91977FB4DA117FEA1685CBDCCBC676AFAEBC6275B8",
          "result": "tesSUCCESS"
        },
        {
          "index": 1,
          "type": "Payment",
          "account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
          "destination": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
          "amountDrops": "1000000",
          "hash": "1CDAF00F1E9B7F65363D777C95E5A168B637B559C2444CAB6290A596ED3313C5",
          "result": "tesSUCCESS"
        }
      ]
    },
    "notes": []
  }
}
```
### batch unfold: GET /v1/batches/CF69AD6ACAEE91600FD54D913D9AB600A7614F57CE99C32AA5B197BF978B6019
```json
{
  "ts": 1792874206,
  "label": "batch unfold",
  "method": "GET",
  "path": "/v1/batches/CF69AD6ACAEE91600FD54D913D9AB600A7614F57CE99C32AA5B197BF978B6019",
  "request": null,
  "status": 200,
  "response": {
    "hash": "CF69AD6ACAEE91600FD54D913D9AB600A7614F57CE99C32AA5B197BF978B6019",
    "validated": true,
    "engineResult": "tesSUCCESS",
    "account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "flags": 65536,
    "legs": [
      {
        "index": 0,
        "type": "Payment",
        "account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
        "destination": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
        "amountDrops": "55000000",
        "hash": "3A5FB051A3020C606140EF91977FB4DA117FEA1685CBDCCBC676AFAEBC6275B8",
        "result": "tesSUCCESS"
      },
      {
        "index": 1,
        "type": "Payment",
        "account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
        "destination": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "amountDrops": "1000000",
        "hash": "1CDAF00F1E9B7F65363D777C95E5A168B637B559C2444CAB6290A596ED3313C5",
        "result": "tesSUCCESS"
      }
    ]
  }
}
```
### working-capital refused: POST /v1/loan-requests
```json
{
  "ts": 1792874211,
  "label": "working-capital refused",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "70000000"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>",
    "disbursement": {
      "supplier": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
      "supplierDrops": "70000000",
      "feeDrops": "1000000",
      "invoice": "INV-WC-1792874206-OVER"
    },
    "signedBatch": "<borrower-signed Batch blob, 776 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0025",
    "ts": 1792874211,
    "kind": "working_capital",
    "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
      "asOf": 1792874208,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 1677,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 3,
        "loanDebtDrops": "126666726",
        "loanPrincipalDrops": "126666668",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "5F093A5F78DBB41EBCEFAC2F1DAD63C1406CA4001A9CBBB5F17D6019CC4D0EBF",
          "5455DB1B49D2B2996C2352B7BDE39E883FF08371D5F55651751982B6EA26EEBF",
          "D28EC92EE4153A5080531429B025161E3984B6B6FAF912992AEEAFD09939202D",
          "E606FD650F5C9E6BE299FEA21ED6C28781E3D236C86C10B9FF6B3B6924F97869",
          "8E1D485B8664038C5E3C6A49CB592382125C33A595C287D81F5A848FC14F843D"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "60000000",
        "termSeconds": 270,
        "existingDebtDrops": "70000000"
      }
    },
    "breakdown": {
      "total": 86,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 90,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 3,
            "points": 0
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 45,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "60000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "70000000",
            "points": 0
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 86,
    "decision": "refuse",
    "status": "refused",
    "reason": "batch_unfunded",
    "loanId": null,
    "txHash": null,
    "engineResult": null,
    "decidedBy": "policy",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": null,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE:6385975",
    "loanSetHash": "6D2772A391A34741FC133947B392B3B1DE948CE6FB57A490683847FE11612DEB",
    "approvalTxHash": null,
    "batch": {
      "supplier": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
      "supplierDrops": "70000000",
      "feeDrops": "1000000",
      "invoice": "INV-WC-1792874206-OVER",
      "hash": null,
      "engineResult": null,
      "legs": []
    },
    "notes": []
  }
}
```
### batch unfold: GET /v1/batches/687B63B5F4F31FA5D884ACEF7F8DE972ADAB9A3DD49B3BA4EAEA12EB2B392533
```json
{
  "ts": 1792874225,
  "label": "batch unfold",
  "method": "GET",
  "path": "/v1/batches/687B63B5F4F31FA5D884ACEF7F8DE972ADAB9A3DD49B3BA4EAEA12EB2B392533",
  "request": null,
  "status": 200,
  "response": {
    "hash": "687B63B5F4F31FA5D884ACEF7F8DE972ADAB9A3DD49B3BA4EAEA12EB2B392533",
    "validated": true,
    "engineResult": "tesSUCCESS",
    "account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
    "flags": 65536,
    "legs": [
      {
        "index": 0,
        "type": "Payment",
        "account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
        "destination": "rMomsiWpgnaSQnHtkWnoFgM93xKP2vAdfp",
        "amountDrops": "241666569",
        "hash": "FC1FE1F272ECC9324FCF25D66D41121B91A43351A23487EDCF237848ADE77542",
        "result": "not_applied"
      },
      {
        "index": 1,
        "type": "Payment",
        "account": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
        "destination": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "amountDrops": "1000000",
        "hash": "983B7868A44235B01768D922A10C20B4AD8ABFADB43D0650E010AD3F0C5D014A",
        "result": "not_applied"
      }
    ]
  }
}
```
### loan default: POST /v1/loans/5D87C185A75EA2E40CDFF053533AEFD46ADAB2A2A40DCDC5B9BE8A2733499144/manage
```json
{
  "ts": 1792874331,
  "label": "loan default",
  "method": "POST",
  "path": "/v1/loans/5D87C185A75EA2E40CDFF053533AEFD46ADAB2A2A40DCDC5B9BE8A2733499144/manage",
  "request": {
    "action": "default"
  },
  "status": 200,
  "response": {
    "loanId": "5D87C185A75EA2E40CDFF053533AEFD46ADAB2A2A40DCDC5B9BE8A2733499144",
    "action": "default",
    "hash": "5777AFE33BA266BD8C898492E18C21A22E3FF25119351BB52F15726632785DF8",
    "engineResult": "tesSUCCESS",
    "coverBeforeDrops": "20000000",
    "coverAfterDrops": "7333333",
    "coverAbsorbedDrops": "12666667",
    "vaultLossDrops": "47333333",
    "defaultAmountDrops": "60000000"
  }
}
```
### loans: GET /v1/loans
```json
{
  "ts": 1792874332,
  "label": "loans",
  "method": "GET",
  "path": "/v1/loans",
  "request": null,
  "status": 200,
  "response": {
    "loans": [
      {
        "loanId": "DFDF6312D4D7F009B28799D2CC8C587EDB5DA696AEFAF21B6D1BD6C67BE59CA3",
        "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
        "principalDrops": "60000000",
        "totalOutstandingDrops": "60000028",
        "periodicPaymentDrops": "20000010",
        "interestRate": 8000,
        "paymentInterval": 90,
        "gracePeriod": 60,
        "nextPaymentDue": 1792874291,
        "paymentRemaining": 3,
        "startDate": 1792874201,
        "status": "active",
        "requestId": "lr_0024",
        "default": null,
        "sweeps": []
      },
      {
        "loanId": "5D87C185A75EA2E40CDFF053533AEFD46ADAB2A2A40DCDC5B9BE8A2733499144",
        "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
        "principalDrops": "0",
        "totalOutstandingDrops": "0",
        "periodicPaymentDrops": "20000010",
        "interestRate": 8000,
        "paymentInterval": 90,
        "gracePeriod": 60,
        "nextPaymentDue": 0,
        "paymentRemaining": 0,
        "startDate": 1792874160,
        "status": "defaulted",
        "requestId": "lr_0022",
        "default": {
          "hash": "5777AFE33BA266BD8C898492E18C21A22E3FF25119351BB52F15726632785DF8",
          "engineResult": "tesSUCCESS",
          "coverBeforeDrops": "20000000",
          "coverAfterDrops": "7333333",
          "coverAbsorbedDrops": "12666667",
          "vaultLossDrops": "47333333",
          "defaultAmountDrops": "60000000",
          "ts": 1792874331
        },
        "sweeps": []
      },
      {
        "loanId": "4F99E62972D556CE84CACB5E45F89DC7AD83FAF6A60EB763FCE2E4CDD0BF2AA9",
        "borrower": "rfWHjXgWTHZzph7oxiXrGkbSnXGRmjScuE",
        "principalDrops": "6666668",
        "totalOutstandingDrops": "6666670",
        "periodicPaymentDrops": "3333335",
        "interestRate": 8000,
        "paymentInterval": 90,
        "gracePeriod": 60,
        "nextPaymentDue": 1792874322,
        "paymentRemaining": 2,
        "startDate": 1792874142,
        "status": "active",
        "requestId": "lr_0021",
        "default": null,
        "sweeps": []
      }
    ],
    "ledgerIndex": 6387682
  }
}
```
### loan-request refused: POST /v1/loan-requests
```json
{
  "ts": 1792874469,
  "label": "loan-request refused",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "15000000"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0026",
    "ts": 1792874469,
    "kind": "loan",
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "60000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
      "asOf": 1792874466,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 28,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 0,
        "loanDebtDrops": "0",
        "loanPrincipalDrops": "0",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "778665100D899A6221732682FC403A54CC8F08E09414A11040EC3BA592ED8E3C",
          "50F750CEE98FE84F0FC92DF1A5B66C83DA2CD79C6B20CD6487767923B4AFB594",
          "48B88C46301DFE752B4AD4A0EAB43F34A6C9DFB60A54787B3997AE5760E80914",
          "743E19AA61D2541A1015C98FA0FB0ECCD2FCFC09A459116E8CBB0651FE6D4279",
          "0D44FABF86906DD591957C0E800505EC61B353C8FACD1EF265EC6725F820CCA9"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "60000000",
        "termSeconds": 270,
        "existingDebtDrops": "15000000"
      }
    },
    "breakdown": {
      "total": 97,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 100,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 0,
            "points": 10
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 70,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "60000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "15000000",
            "points": 25
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 97,
    "decision": "refuse",
    "status": "refused",
    "reason": "vault_utilization",
    "loanId": null,
    "txHash": null,
    "engineResult": null,
    "decidedBy": "policy",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": null,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG:6387694",
    "loanSetHash": "983B66D09E595E5BB68DBB8AAC018B83C0348400559C735B67574917CD24120D",
    "approvalTxHash": null,
    "notes": []
  }
}
```
### loan-request held: POST /v1/loan-requests
```json
{
  "ts": 1792874483,
  "label": "loan-request held",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "25000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "5000000"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0027",
    "ts": 1792874483,
    "kind": "loan",
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "25000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
      "asOf": 1792874480,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 32,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 0,
        "loanDebtDrops": "0",
        "loanPrincipalDrops": "0",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "778665100D899A6221732682FC403A54CC8F08E09414A11040EC3BA592ED8E3C",
          "50F750CEE98FE84F0FC92DF1A5B66C83DA2CD79C6B20CD6487767923B4AFB594",
          "48B88C46301DFE752B4AD4A0EAB43F34A6C9DFB60A54787B3997AE5760E80914",
          "743E19AA61D2541A1015C98FA0FB0ECCD2FCFC09A459116E8CBB0651FE6D4279",
          "0D44FABF86906DD591957C0E800505EC61B353C8FACD1EF265EC6725F820CCA9"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "25000000",
        "termSeconds": 270,
        "existingDebtDrops": "5000000"
      }
    },
    "breakdown": {
      "total": 97,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 100,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 0,
            "points": 10
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 70,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "25000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "5000000",
            "points": 25
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 97,
    "decision": "hold",
    "status": "held",
    "reason": "over_auto_limit",
    "loanId": null,
    "txHash": null,
    "engineResult": null,
    "decidedBy": "policy",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": 3,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG:6387694",
    "loanSetHash": "231F255B07CAFAB987EB0A551C23B2FB6BFA0F9733A22628DDC4C86DEDC1D4B4",
    "approvalTxHash": null,
    "notes": []
  }
}
```
### deny: POST /v1/loan-requests/lr_0027/deny
```json
{
  "ts": 1792874489,
  "label": "deny",
  "method": "POST",
  "path": "/v1/loan-requests/lr_0027/deny",
  "request": {
    "reason": null
  },
  "status": 200,
  "response": {
    "id": "lr_0027",
    "ts": 1792874483,
    "kind": "loan",
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "25000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
      "asOf": 1792874480,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 32,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 0,
        "loanDebtDrops": "0",
        "loanPrincipalDrops": "0",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "778665100D899A6221732682FC403A54CC8F08E09414A11040EC3BA592ED8E3C",
          "50F750CEE98FE84F0FC92DF1A5B66C83DA2CD79C6B20CD6487767923B4AFB594",
          "48B88C46301DFE752B4AD4A0EAB43F34A6C9DFB60A54787B3997AE5760E80914",
          "743E19AA61D2541A1015C98FA0FB0ECCD2FCFC09A459116E8CBB0651FE6D4279",
          "0D44FABF86906DD591957C0E800505EC61B353C8FACD1EF265EC6725F820CCA9"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "25000000",
        "termSeconds": 270,
        "existingDebtDrops": "5000000"
      }
    },
    "breakdown": {
      "total": 97,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 100,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 0,
            "points": 10
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 70,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "25000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "5000000",
            "points": 25
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 97,
    "decision": "hold",
    "status": "denied",
    "reason": "denied_by_human",
    "loanId": null,
    "txHash": null,
    "engineResult": null,
    "decidedBy": "human",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": 3,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG:6387694",
    "loanSetHash": "231F255B07CAFAB987EB0A551C23B2FB6BFA0F9733A22628DDC4C86DEDC1D4B4",
    "approvalTxHash": null,
    "notes": []
  }
}
```
### loan-request auto: POST /v1/loan-requests
```json
{
  "ts": 1792874513,
  "label": "loan-request auto",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "10000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "5000000"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0028",
    "ts": 1792874508,
    "kind": "loan",
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "10000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
      "asOf": 1792874505,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 38,
        "inboundPaymentCount": 24,
        "inboundVolumeDrops": "61000000",
        "distinctPayers": 5,
        "topPayerSharePct": 31.1,
        "activeDays": 22,
        "activeLoans": 0,
        "loanDebtDrops": "0",
        "loanPrincipalDrops": "0",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "778665100D899A6221732682FC403A54CC8F08E09414A11040EC3BA592ED8E3C",
          "50F750CEE98FE84F0FC92DF1A5B66C83DA2CD79C6B20CD6487767923B4AFB594",
          "48B88C46301DFE752B4AD4A0EAB43F34A6C9DFB60A54787B3997AE5760E80914",
          "743E19AA61D2541A1015C98FA0FB0ECCD2FCFC09A459116E8CBB0651FE6D4279",
          "0D44FABF86906DD591957C0E800505EC61B353C8FACD1EF265EC6725F820CCA9"
        ],
        "memoDatedPayments": 24,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "61000000",
        "x402Payments": 24,
        "x402Payers": 5,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "10000000",
        "termSeconds": 270,
        "existingDebtDrops": "5000000"
      }
    },
    "breakdown": {
      "total": 99,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 100,
        "rules": [
          {
            "rule": "activeDays",
            "value": 22,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "61000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 5,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 31.1,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 0,
            "points": 10
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 85,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "10000000",
            "points": 40
          },
          {
            "rule": "existingDebtToVolume",
            "value": "5000000",
            "points": 25
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 99,
    "decision": "auto",
    "status": "auto",
    "reason": null,
    "loanId": "D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8",
    "txHash": "8E68B713EF74480B71D749BAC123480B366A824CCA4569B13757E1F74304D593",
    "engineResult": "tesSUCCESS",
    "decidedBy": "policy",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": 0,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG:6387694",
    "loanSetHash": "1E7D16F717175531134195228549BAE542B8B06BCBCD65427DB2352DD23C9343",
    "approvalTxHash": null,
    "notes": []
  }
}
```
### sweep repaid: POST /v1/loans/D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8/sweeps
```json
{
  "ts": 1792874541,
  "label": "sweep repaid",
  "method": "POST",
  "path": "/v1/loans/D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8/sweeps",
  "request": {
    "incomeHash": "08D4B46C31C611BFC22617EB06BE3F154D3D929BD74D6A4A720A5FCF37A964E9",
    "incomeDrops": "5000000",
    "payer": "rByBccT5CSXGuC1LnxiNtzaXYjGZm3MTq1",
    "loanId": "D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8",
    "loanPayHash": "E276E391D2979A899D85CCDADEC9E48101EB94DA7B9A4E724BC4CEF4A584BF75",
    "drops": "3333335",
    "engineResult": "tesSUCCESS",
    "ledgerIndex": 6387742,
    "at": 1792874531
  },
  "status": 200,
  "response": {
    "loanId": "D85727CF74F87EE47259FEB6555049795BCA56149B6E3CA0F88D0336D6B688F8",
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "loanPayHash": "E276E391D2979A899D85CCDADEC9E48101EB94DA7B9A4E724BC4CEF4A584BF75",
    "incomeHash": "08D4B46C31C611BFC22617EB06BE3F154D3D929BD74D6A4A720A5FCF37A964E9",
    "incomeDrops": "5000000",
    "payer": "rByBccT5CSXGuC1LnxiNtzaXYjGZm3MTq1",
    "drops": "3333335",
    "engineResult": "tesSUCCESS",
    "status": "repaid",
    "ledgerIndex": 6387742,
    "at": 1792874531,
    "verifiedAt": 1792874541
  }
}
```
### loan-request held: POST /v1/loan-requests
```json
{
  "ts": 1792875966,
  "label": "loan-request held",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "rBvEzCJwLm39v57JE29e4Yi7rszqmfYFZs",
    "principalDrops": "2000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "0"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0029",
    "ts": 1792875966,
    "kind": "loan",
    "borrower": "rBvEzCJwLm39v57JE29e4Yi7rszqmfYFZs",
    "principalDrops": "2000000",
    "termSeconds": 270,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rBvEzCJwLm39v57JE29e4Yi7rszqmfYFZs",
      "asOf": 1792875943,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 87,
        "inboundPaymentCount": 3,
        "inboundVolumeDrops": "15000000",
        "distinctPayers": 3,
        "topPayerSharePct": 33.3,
        "activeDays": 1,
        "activeLoans": 0,
        "loanDebtDrops": "0",
        "loanPrincipalDrops": "0",
        "pastDefaults": 0,
        "hasAcceptedCredential": false,
        "sampleTxHashes": [
          "8F9B4B72461BB4E59D1B13875D1148872E157C2984C4E46370C60CB11CFE50C4",
          "921D40581EDC1B5D06808B5EAE17313E84026A84B2D982DFAFC7B0C04AEE7785",
          "7A2D8D1F8A91252C034475723E793C4D5805F7B5F69799BDCC194F2D6C9238F2"
        ],
        "memoDatedPayments": 3,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "15000000",
        "x402Payments": 3,
        "x402Payers": 3,
        "otherInboundDrops": "0"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "2000000",
        "termSeconds": 270,
        "existingDebtDrops": "0"
      }
    },
    "breakdown": {
      "total": 43,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 37,
        "rules": [
          {
            "rule": "activeDays",
            "value": 1,
            "points": 0
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "15000000",
            "points": 0
          },
          {
            "rule": "distinctPayers",
            "value": 3,
            "points": 7
          },
          {
            "rule": "topPayerSharePct",
            "value": 33.3,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 0,
            "points": 10
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": false,
            "points": 0
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 100,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "2000000",
            "points": 40
          },
          {
            "rule": "existingDebtToVolume",
            "value": "0",
            "points": 40
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 270,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 43,
    "decision": "hold",
    "status": "held",
    "reason": "score_below_auto",
    "loanId": null,
    "txHash": null,
    "engineResult": null,
    "decidedBy": "policy",
    "memo": null,
    "secondOpinion": null,
    "secondOpinionMs": 20031,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rBvEzCJwLm39v57JE29e4Yi7rszqmfYFZs:6388068",
    "loanSetHash": "E96F8AE74C7054F7380405E35570C3495E7A1AFDA058AF051ABF3FA3CD29EAAE",
    "approvalTxHash": null,
    "notes": []
  }
}
```
### credential tesSUCCESS: POST /v1/broker/credentials
```json
{
  "ts": 1792877266,
  "label": "credential tesSUCCESS",
  "method": "POST",
  "path": "/v1/broker/credentials",
  "request": {
    "subject": "rwNfF12NjdqrPhpmzGGaeKAHWzMfpej4z8"
  },
  "status": 200,
  "response": {
    "hash": "590FD1455CCC76AB872E1BA2CF90282C4D55378A8B95610372C11A0104B20A6E",
    "engineResult": "tesSUCCESS"
  }
}
```
### credential tesSUCCESS: POST /v1/broker/credentials
```json
{
  "ts": 1792877496,
  "label": "credential tesSUCCESS",
  "method": "POST",
  "path": "/v1/broker/credentials",
  "request": {
    "subject": "r3nHvBa1q97LtEYkoQPp2RsSZaSnNQBMNh"
  },
  "status": 200,
  "response": {
    "hash": "D7576539A2EA2B4A73CD38B74291515FE53B3549A815800E0D1FDB1E92663148",
    "engineResult": "tesSUCCESS"
  }
}
```
### working-capital held: POST /v1/loan-requests
```json
{
  "ts": 1792879647,
  "label": "working-capital held",
  "method": "POST",
  "path": "/v1/loan-requests",
  "request": {
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "30000000",
    "termSeconds": 540,
    "purpose": "inventory",
    "declared": {
      "existingDebtDrops": "6666668"
    },
    "signedLoanSet": "<borrower-signed LoanSet blob, 480 hex chars>",
    "disbursement": {
      "supplier": "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai",
      "supplierDrops": "29000000",
      "feeDrops": "1000000",
      "invoice": "GPU-COMPUTE-HOURS-1"
    },
    "signedBatch": "<borrower-signed Batch blob, 770 hex chars>"
  },
  "status": 200,
  "response": {
    "id": "lr_0030",
    "ts": 1792879647,
    "kind": "working_capital",
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "30000000",
    "termSeconds": 540,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
      "asOf": 1792879638,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 1531,
        "inboundPaymentCount": 25,
        "inboundVolumeDrops": "66000000",
        "distinctPayers": 6,
        "topPayerSharePct": 28.8,
        "activeDays": 23,
        "activeLoans": 1,
        "loanDebtDrops": "6666670",
        "loanPrincipalDrops": "6666668",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "08D4B46C31C611BFC22617EB06BE3F154D3D929BD74D6A4A720A5FCF37A964E9",
          "778665100D899A6221732682FC403A54CC8F08E09414A11040EC3BA592ED8E3C",
          "50F750CEE98FE84F0FC92DF1A5B66C83DA2CD79C6B20CD6487767923B4AFB594",
          "48B88C46301DFE752B4AD4A0EAB43F34A6C9DFB60A54787B3997AE5760E80914",
          "743E19AA61D2541A1015C98FA0FB0ECCD2FCFC09A459116E8CBB0651FE6D4279"
        ],
        "memoDatedPayments": 25,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "66000000",
        "x402Payments": 25,
        "x402Payers": 6,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "30000000",
        "termSeconds": 540,
        "existingDebtDrops": "6666668"
      }
    },
    "breakdown": {
      "total": 88,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 90,
        "rules": [
          {
            "rule": "activeDays",
            "value": 23,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "66000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 6,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 28.8,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 1,
            "points": 0
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 70,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "30000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "6666668",
            "points": 25
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 540,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 88,
    "decision": "hold",
    "status": "held",
    "reason": "over_auto_limit",
    "loanId": null,
    "txHash": null,
    "engineResult": null,
    "decidedBy": "policy",
    "memo": "The 23 active days come from payment memo dates (all 25 payments\u2026(465 chars)",
    "secondOpinion": {
      "recommendation": "hold",
      "memo": "The 23 active days come from payment memo dates (all 25 payments\u2026(465 chars)",
      "flags": [
        "fresh_account",
        "thin_history",
        "memo_dated_activity",
        "open_loan",
        "above_auto_limit",
        "large_vs_vault"
      ]
    },
    "secondOpinionMs": 6642,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG:6387696",
    "loanSetHash": "70C795FCADB20C0FE1EC53F722817476B2738853C7F448E3254C5205F616E646",
    "approvalTxHash": null,
    "batch": {
      "supplier": "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai",
      "supplierDrops": "29000000",
      "feeDrops": "1000000",
      "invoice": "GPU-COMPUTE-HOURS-1",
      "hash": null,
      "engineResult": null,
      "legs": []
    },
    "notes": []
  }
}
```
### working-capital approve approved: POST /v1/loan-requests/lr_0030/approve
```json
{
  "ts": 1792879677,
  "label": "working-capital approve approved",
  "method": "POST",
  "path": "/v1/loan-requests/lr_0030/approve",
  "request": {},
  "status": 200,
  "response": {
    "id": "lr_0030",
    "ts": 1792879647,
    "kind": "working_capital",
    "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
    "principalDrops": "30000000",
    "termSeconds": 540,
    "purpose": "inventory",
    "evidence": {
      "borrower": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
      "asOf": 1792879638,
      "windowDays": 30,
      "ledger": {
        "accountExists": true,
        "accountAgeLedgers": 1531,
        "inboundPaymentCount": 25,
        "inboundVolumeDrops": "66000000",
        "distinctPayers": 6,
        "topPayerSharePct": 28.8,
        "activeDays": 23,
        "activeLoans": 1,
        "loanDebtDrops": "6666670",
        "loanPrincipalDrops": "6666668",
        "pastDefaults": 0,
        "hasAcceptedCredential": true,
        "sampleTxHashes": [
          "08D4B46C31C611BFC22617EB06BE3F154D3D929BD74D6A4A720A5FCF37A964E9",
          "778665100D899A6221732682FC403A54CC8F08E09414A11040EC3BA592ED8E3C",
          "50F750CEE98FE84F0FC92DF1A5B66C83DA2CD79C6B20CD6487767923B4AFB594",
          "48B88C46301DFE752B4AD4A0EAB43F34A6C9DFB60A54787B3997AE5760E80914",
          "743E19AA61D2541A1015C98FA0FB0ECCD2FCFC09A459116E8CBB0651FE6D4279"
        ],
        "memoDatedPayments": 25,
        "ledgerActiveDays": 1,
        "x402IncomeDrops": "66000000",
        "x402Payments": 25,
        "x402Payers": 6,
        "otherInboundDrops": "0",
        "credentialIssuer": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
        "credentialType": "kyb-borrower"
      },
      "bank": null,
      "declared": {
        "purpose": "inventory",
        "principalDrops": "30000000",
        "termSeconds": 540,
        "existingDebtDrops": "6666668"
      }
    },
    "breakdown": {
      "total": 88,
      "weights": {
        "ledger": 90,
        "bank": 0,
        "declared": 10
      },
      "ledger": {
        "score": 90,
        "rules": [
          {
            "rule": "activeDays",
            "value": 23,
            "points": 20
          },
          {
            "rule": "inboundVolumeDrops",
            "value": "66000000",
            "points": 20
          },
          {
            "rule": "distinctPayers",
            "value": 6,
            "points": 15
          },
          {
            "rule": "topPayerSharePct",
            "value": 28.8,
            "points": 10
          },
          {
            "rule": "activeLoans",
            "value": 1,
            "points": 0
          },
          {
            "rule": "pastDefaults",
            "value": 0,
            "points": 10
          },
          {
            "rule": "hasAcceptedCredential",
            "value": true,
            "points": 15
          }
        ]
      },
      "bank": null,
      "declared": {
        "score": 70,
        "rules": [
          {
            "rule": "principalToVolume",
            "value": "30000000",
            "points": 25
          },
          {
            "rule": "existingDebtToVolume",
            "value": "6666668",
            "points": 25
          },
          {
            "rule": "purpose",
            "value": "inventory",
            "points": 10
          },
          {
            "rule": "termSeconds",
            "value": 540,
            "points": 10
          }
        ]
      },
      "capped": null
    },
    "score": 88,
    "decision": "hold",
    "status": "approved",
    "reason": "over_auto_limit",
    "loanId": "61AA9DFAE4A68286FBE8D905FDF818D54E59E11D71BDF291DCE777BFCAD430F0",
    "txHash": "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13",
    "engineResult": "tesSUCCESS",
    "decidedBy": "ledger",
    "memo": "The 23 active days come from payment memo dates (all 25 payments\u2026(465 chars)",
    "secondOpinion": {
      "recommendation": "hold",
      "memo": "The 23 active days come from payment memo dates (all 25 payments\u2026(465 chars)",
      "flags": [
        "fresh_account",
        "thin_history",
        "memo_dated_activity",
        "open_loan",
        "above_auto_limit",
        "large_vs_vault"
      ]
    },
    "secondOpinionMs": 6642,
    "policyHash": "c18f11634a06502a",
    "blobKey": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG:6387696",
    "loanSetHash": "70C795FCADB20C0FE1EC53F722817476B2738853C7F448E3254C5205F616E646",
    "approvalTxHash": "8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C",
    "batch": {
      "supplier": "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai",
      "supplierDrops": "29000000",
      "feeDrops": "1000000",
      "invoice": "GPU-COMPUTE-HOURS-1",
      "hash": "6C506E2B9E7B6027C9BBC80E6A75480A1DF2382346567F0BD98E60A540A29DDB",
      "engineResult": "tesSUCCESS",
      "legs": [
        {
          "index": 0,
          "type": "Payment",
          "account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
          "destination": "r3ojz3wRg78u5mEhsaWHZxHVPgMV6SiYai",
          "amountDrops": "29000000",
          "hash": "EB3922C3198E1B7891F12B4323B6B696CE10834D0E17DE66A218AF8119E618FE",
          "result": "tesSUCCESS"
        },
        {
          "index": 1,
          "type": "Payment",
          "account": "rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG",
          "destination": "rEH59tesggzmgg42PeHvByQQ3kmUNhegVw",
          "amountDrops": "1000000",
          "hash": "1760EA4403177EF90BEBF8EE1509777E810DD25FCBBB54F71B83E52ABDCE5CD6",
          "result": "tesSUCCESS"
        }
      ]
    },
    "notes": [
      {
        "from": "borrower-agent",
        "text": "I'm asking for 30 XRP, which is the 29 XRP GPU-COMPUTE-HOURS-1 i\u2026(318 chars)",
        "ts": 1792879647
      },
      {
        "from": "borrower-agent",
        "text": "lr_0030 is held (over_auto_limit): Held for you. 30 XRP is more \u2026(186 chars)",
        "ts": 1792879647
      }
    ],
    "recheckPolicyHash": "c18f11634a06502a"
  }
}
```
