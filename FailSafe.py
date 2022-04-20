import pandas as pd
import gspread
import requests
from tenacity import retry, wait_fixed
from datetime import datetime, timedelta


@retry(wait=wait_fixed(4))
def manifest_search(manifest_id):
    url = f"https://api-ca.metrc.com//transfers/v1/{manifest_id}/deliveries"

    payload = {}
    headers = {
        "Authorization": "Basic bE9ibFlIRlFhYlR2bU9Vb01TTFRDbTkyRjNTcE1ndW5Pdm5oTWtUZGJXZzhUbWRxOm14MTU5a2VnVE1zT2U1ejFWcE5iR1plLU1EdGRPNUFjbkxMcmRtSDE5b3JVaVB3cA=="
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    try:
        return response.json()[0]["DeliveryPackageCount"]
    except:
        return False


yesterday = datetime.now() - timedelta(1)
yesterday = datetime.strftime(yesterday, "%Y-%m-%d")
gc = gspread.service_account(
    filename=r"D:\1. Programiranje\1. Klijenti\METRCxNABIS-Automation\emailsending-325211-e5456e88f282.json"
)

sh = gc.open_by_url(
    "https://docs.google.com/spreadsheets/d/1LkP08iIUIZyRz-_C45AJ0FvRJuwGK_SzuZylfNMrAuE"
)
wks = sh.worksheet("Logs")
sheet_df = pd.DataFrame(wks.get_all_records())

sheet_df = sheet_df[sheet_df["Date"] == yesterday]

print(f"First idx: {sheet_df.index[0]}, last idx: {sheet_df.index[-1]}")

for idx, row in sheet_df.iterrows():
    if sheet_df.loc[idx, "ALL_GOOD"] == "TRUE":
        print(f"{idx} out of {sheet_df.index[-1]}")
        sheet_df.loc[idx, "MetrcPkg"] = manifest_search(int(row["ManifestId"]))
        if sheet_df.loc[idx, "MetrcPkg"] != sheet_df.loc[idx, "PkgNbr"]:
            sheet_df.loc[idx, "PkgComparissonStatus"] = "FALSE"
        else:
            sheet_df.loc[idx, "PkgComparissonStatus"] = "TRUE"

sheet_df.drop(sheet_df.columns[[]])
print("SUCESSS")
upload_df = sheet_df[
    [
        "Date",
        "Timestamp",
        "Order",
        "Shipment",
        "ALL_GOOD",
        "ManifestId",
        "InternalTransfer",
        "TransferType",
        "PkgNbr",
        "Duration(S)",
        "MissingPackageTag",
        "MissingChildPackageTag",
        "PricesEmpty",
        "IncorrectPkgNbr",
        "TransportMatchAction",
        "OrderNote",
        "Warehouse",
        "MetrcPkg",
        "PkgComparissonStatus",
    ]
][sheet_df["Date"] == yesterday]

wks = sh.worksheet("DailyPkgCompare")
upload_df.fillna("", inplace=True)
wks.update([upload_df.columns.values.tolist()] + upload_df.values.tolist())
