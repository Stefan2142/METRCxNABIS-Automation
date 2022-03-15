import requests
from api_calls import view_metrc_transfer, get_order_data

import requests

url = "https://api.getnabis.com/graphql/admin"

payload = {
    "operations": '{"operationName":"updateMetrcTransfer","variables":{"id":"TWV0cmNUcmFuc2Zlcjo3ZDkxNzVmZC1jNzU1LTRiZmYtOGU5MS01MWM1MmQwZjQxMWI=","metrcManifestFile":null},"query":"mutation updateMetrcTransfer($id: ID!, $metrcManifestId: Int, $metrcTransferTemplateName: String, $metrcManifestS3FileLink: String, $metrcOrderNotes: String, $metrcManifestFile: Upload) {\\n  updateMetrcTransfer(id: $id, metrcManifestId: $metrcManifestId, metrcTransferTemplateName: $metrcTransferTemplateName, metrcManifestS3FileLink: $metrcManifestS3FileLink, metrcOrderNotes: $metrcOrderNotes, metrcManifestFile: $metrcManifestFile) {\\n    ...metrcTransferFragment\\n    __typename\\n  }\\n}\\n\\nfragment metrcTransferFragment on MetrcTransfer {\\n  id\\n  orderId\\n  order {\\n    id\\n    metrcWarehouseLicenseNumber\\n    __typename\\n  }\\n  originLicensedLocationId\\n  originLicensedLocation {\\n    ...licensedLocationFragment\\n    __typename\\n  }\\n  destinationLicensedLocationId\\n  destinationLicensedLocation {\\n    ...licensedLocationFragment\\n    __typename\\n  }\\n  metrcManifestId\\n  metrcTransferTemplateName\\n  metrcManifestS3FileLink\\n  metrcOrderNotes\\n  shipmentId\\n  shipment {\\n    ...shipmentFragment\\n    __typename\\n  }\\n  creatorId\\n  creator {\\n    id\\n    email\\n    __typename\\n  }\\n  createdAt\\n  updatedAt\\n  __typename\\n}\\n\\nfragment licensedLocationFragment on LicensedLocation {\\n  id\\n  name\\n  address1\\n  address2\\n  city\\n  state\\n  zip\\n  siteCategory\\n  lat\\n  lng\\n  billingAddress1\\n  billingAddress2\\n  billingAddressCity\\n  billingAddressState\\n  billingAddressZip\\n  warehouseId\\n  isArchived\\n  doingBusinessAs\\n  noExciseTax\\n  phoneNumber\\n  printCoas\\n  hoursBusiness\\n  hoursDelivery\\n  deliveryByApptOnly\\n  specialProtocol\\n  schedulingSoftwareRequired\\n  schedulingSoftwareLink\\n  centralizedPurchasingNotes\\n  payByCheck\\n  collectionNotes\\n  deliveryNotes\\n  collect1PocFirstName\\n  collect1PocLastName\\n  collect1PocTitle\\n  collect1PocNumber\\n  collect1PocEmail\\n  collect1PocAllowsText\\n  collect1PreferredContactMethod\\n  collect2PocFirstName\\n  collect2PocLastName\\n  collect2PocTitle\\n  collect2PocNumber\\n  collect2PocEmail\\n  collect2PocAllowsText\\n  collect2PreferredContactMethod\\n  delivery1PocFirstName\\n  delivery1PocLastName\\n  delivery1PocTitle\\n  delivery1PocNumber\\n  delivery1PocEmail\\n  delivery1PocAllowsText\\n  delivery1PreferredContactMethod\\n  delivery2PocFirstName\\n  delivery2PocLastName\\n  delivery2PocTitle\\n  delivery2PocNumber\\n  delivery2PocEmail\\n  delivery2PocAllowsText\\n  delivery2PreferredContactMethod\\n  unmaskedId\\n  qualitativeRating\\n  creditRating\\n  trustLevelNabis\\n  trustLevelInEffect\\n  isOnNabisTracker\\n  locationNotes\\n  infoplus\\n  w9Link\\n  taxIdentificationNumber\\n  sellerPermitLink\\n  nabisMaxTerms\\n  __typename\\n}\\n\\nfragment shipmentFragment on Shipment {\\n  id\\n  orderId\\n  originLicensedLocationId\\n  destinationLicensedLocationId\\n  status\\n  stagingAreaId\\n  isUnloaded\\n  unloaderId\\n  isLoaded\\n  loaderId\\n  arrivalTime\\n  departureTime\\n  isShipped\\n  vehicleId\\n  driverId\\n  previousShipmentId\\n  nextShipmentId\\n  infoplusOrderId\\n  infoplusAsnId\\n  infoplusOrderInventoryStatus\\n  infoplusAsnInventoryStatus\\n  createdAt\\n  updatedAt\\n  shipmentNumber\\n  queueOrder\\n  isStaged\\n  isPrinted\\n  arrivalTimeAfter\\n  arrivalTimeBefore\\n  fulfillability\\n  pickers\\n  shipmentType\\n  intaken\\n  outtaken\\n  metrcWarehouseLicenseNumber\\n  __typename\\n}\\n"}',
    "map": '{"1":["variables.metrcManifestFile"]}',
}
files = [
    (
        "1",
        (
            "TransferManifest (1).pdf",
            open("TransferManifest (1).pdf", "rb"),
            "application/octet-stream",
        ),
    )
]
headers = {
    "authority": "api.getnabis.com",
    "accept": "*/*",
    "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2NDc3MjkwOTQsImlzQWRtaW4iOnRydWUsImlzRHJpdmVyIjpmYWxzZSwiaWF0IjoxNjQ2NDMzMDk0LCJhdWQiOiJhZG1pbiIsImlzcyI6Imh0dHBzOi8vZ2V0bmFiaXMuY29tIiwic3ViIjoiZDI0NDczZDctNzBjZS00N2M4LTg1OTItOWVlY2Q0NzgzMDQ0In0.k5zC5b_LSxLjLMlYVFc-qIKos56PIDvUdutKEHDlMLw",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",
    "sec-gpc": "1",
    "origin": "https://app.getnabis.com",
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://app.getnabis.com/",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
}

response = requests.request("POST", url, headers=headers, data=payload, files=files)

print(response.text)


exit(1)
columns = [
    "Date",
    "Order",
    "PackageMissing",
    "IncorrectLicense",
    "IncorrectDates",
    "IncorrectDriver",
    "IncorrectDriverId",
    "IncorrectVehicleMake",
    "IncorrectVehicleModel",
    "IncorrectVehicleMake",
    "CantFindRoute",
    "IncorrectPkgNbr",
    "MissingPackageTag",
    "WrongQuantity",
    "WrongPrice",
    "ALL_GOOD",
]


import gspread
import pandas as pd

gc = gspread.service_account(filename="./emailsending-325211-e5456e88f282.json")
sh = gc.open_by_url(
    "https://docs.google.com/spreadsheets/d/1LkP08iIUIZyRz-_C45AJ0FvRJuwGK_SzuZylfNMrAuE"
)
wks = sh.worksheet("Logs")
sheet_df = pd.DataFrame(wks.get_all_records(head=0))
df = pd.DataFrame(columns=columns)

sheet_data = sheet_df.values.tolist()
# wks.append_rows(sheet_data)

exit(1)
o = get_order_data(142358)
transfer = view_metrc_transfer(o["id"])
transfer["data"]["getMetrcTransfers"][0]["id"]
# manifest_id = [x['getMetrcTransfer'][0]['id'] for x in transfer if 'getMetrcTransfer' in x.keys()]


"https://docs.google.com/spreadsheets/d/1LkP08iIUIZyRz-_C45AJ0FvRJuwGK_SzuZylfNMrAuE/edit?usp=sharing"


exit(1)
url = "https://api.getnabis.com/graphql/admin"


def upload_manifest_pdf(manifest_id):
    payload = {
        "operations": '{"operationName":"updateMetrcTransfer","variables":{"id":"{manifest_id}","metrcManifestFile":null},"query":"mutation updateMetrcTransfer($id: ID!, $metrcManifestId: Int, $metrcTransferTemplateName: String, $metrcManifestS3FileLink: String, $metrcOrderNotes: String, $metrcManifestFile: Upload) {\\n  updateMetrcTransfer(id: $id, metrcManifestId: $metrcManifestId, metrcTransferTemplateName: $metrcTransferTemplateName, metrcManifestS3FileLink: $metrcManifestS3FileLink, metrcOrderNotes: $metrcOrderNotes, metrcManifestFile: $metrcManifestFile) {\\n    ...metrcTransferFragment\\n    __typename\\n  }\\n}\\n\\nfragment metrcTransferFragment on MetrcTransfer {\\n  id\\n  orderId\\n  order {\\n    id\\n    metrcWarehouseLicenseNumber\\n    __typename\\n  }\\n  originLicensedLocationId\\n  originLicensedLocation {\\n    ...licensedLocationFragment\\n    __typename\\n  }\\n  destinationLicensedLocationId\\n  destinationLicensedLocation {\\n    ...licensedLocationFragment\\n    __typename\\n  }\\n  metrcManifestId\\n  metrcTransferTemplateName\\n  metrcManifestS3FileLink\\n  metrcOrderNotes\\n  shipmentId\\n  shipment {\\n    ...shipmentFragment\\n    __typename\\n  }\\n  creatorId\\n  creator {\\n    id\\n    email\\n    __typename\\n  }\\n  createdAt\\n  updatedAt\\n  __typename\\n}\\n\\nfragment licensedLocationFragment on LicensedLocation {\\n  id\\n  name\\n  address1\\n  address2\\n  city\\n  state\\n  zip\\n  siteCategory\\n  lat\\n  lng\\n  billingAddress1\\n  billingAddress2\\n  billingAddressCity\\n  billingAddressState\\n  billingAddressZip\\n  warehouseId\\n  isArchived\\n  doingBusinessAs\\n  noExciseTax\\n  phoneNumber\\n  printCoas\\n  hoursBusiness\\n  hoursDelivery\\n  deliveryByApptOnly\\n  specialProtocol\\n  schedulingSoftwareRequired\\n  schedulingSoftwareLink\\n  centralizedPurchasingNotes\\n  payByCheck\\n  collectionNotes\\n  deliveryNotes\\n  collect1PocFirstName\\n  collect1PocLastName\\n  collect1PocTitle\\n  collect1PocNumber\\n  collect1PocEmail\\n  collect1PocAllowsText\\n  collect1PreferredContactMethod\\n  collect2PocFirstName\\n  collect2PocLastName\\n  collect2PocTitle\\n  collect2PocNumber\\n  collect2PocEmail\\n  collect2PocAllowsText\\n  collect2PreferredContactMethod\\n  delivery1PocFirstName\\n  delivery1PocLastName\\n  delivery1PocTitle\\n  delivery1PocNumber\\n  delivery1PocEmail\\n  delivery1PocAllowsText\\n  delivery1PreferredContactMethod\\n  delivery2PocFirstName\\n  delivery2PocLastName\\n  delivery2PocTitle\\n  delivery2PocNumber\\n  delivery2PocEmail\\n  delivery2PocAllowsText\\n  delivery2PreferredContactMethod\\n  unmaskedId\\n  qualitativeRating\\n  creditRating\\n  trustLevelNabis\\n  trustLevelInEffect\\n  isOnNabisTracker\\n  locationNotes\\n  infoplus\\n  w9Link\\n  taxIdentificationNumber\\n  sellerPermitLink\\n  nabisMaxTerms\\n  __typename\\n}\\n\\nfragment shipmentFragment on Shipment {\\n  id\\n  orderId\\n  originLicensedLocationId\\n  destinationLicensedLocationId\\n  status\\n  stagingAreaId\\n  isUnloaded\\n  unloaderId\\n  isLoaded\\n  loaderId\\n  arrivalTime\\n  departureTime\\n  isShipped\\n  vehicleId\\n  driverId\\n  previousShipmentId\\n  nextShipmentId\\n  infoplusOrderId\\n  infoplusAsnId\\n  infoplusOrderInventoryStatus\\n  infoplusAsnInventoryStatus\\n  createdAt\\n  updatedAt\\n  shipmentNumber\\n  queueOrder\\n  isStaged\\n  isPrinted\\n  arrivalTimeAfter\\n  arrivalTimeBefore\\n  fulfillability\\n  pickers\\n  shipmentType\\n  intaken\\n  outtaken\\n  metrcWarehouseLicenseNumber\\n  __typename\\n}\\n"}'.format(
            manifest_id
        ),
        "map": '{"1":["variables.metrcManifestFile"]}',
    }
    files = [
        (
            "1",
            (
                "TransferManifest 0003194514.pdf",
                open("TransferManifest 0003194514.pdf", "rb"),
                "application/pdf",
            ),
        )
    ]
    headers = {
        "authority": "api.getnabis.com",
        "accept": "*/*",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2NDc1NDc2OTQsImlzQWRtaW4iOnRydWUsImlzRHJpdmVyIjpmYWxzZSwiaWF0IjoxNjQ2MjUxNjk0LCJhdWQiOiJhZG1pbiIsImlzcyI6Imh0dHBzOi8vZ2V0bmFiaXMuY29tIiwic3ViIjoiZDI0NDczZDctNzBjZS00N2M4LTg1OTItOWVlY2Q0NzgzMDQ0In0.NtpfYpR5ALSiOc4FeWuIxVshfRtdpGZ4A6TcthtVwt0",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
        "sec-gpc": "1",
        "origin": "https://app.getnabis.com",
        "sec-fetch-site": "same-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://app.getnabis.com/",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    }

    response = requests.request("POST", url, headers=headers, data=payload, files=files)

    print(response.text)


def upload_manifest_id():

    url = "https://api.getnabis.com/graphql/admin"

    payload = json.dumps(
        [
            {
                "operationName": "updateMetrcTransfer",
                "variables": {
                    "id": "TWV0cmNUcmFuc2ZlcjpjNGE1Mjk0MS0xYzlmLTQ2NzctOGVlMS0xZTMxNjk1MDBkZTg=",
                    "metrcManifestId": 3194514,
                },
                "query": "mutation updateMetrcTransfer($id: ID!, $metrcManifestId: Int, $metrcTransferTemplateName: String, $metrcManifestS3FileLink: String, $metrcOrderNotes: String, $metrcManifestFile: Upload) {\n  updateMetrcTransfer(id: $id, metrcManifestId: $metrcManifestId, metrcTransferTemplateName: $metrcTransferTemplateName, metrcManifestS3FileLink: $metrcManifestS3FileLink, metrcOrderNotes: $metrcOrderNotes, metrcManifestFile: $metrcManifestFile) {\n    ...metrcTransferFragment\n    __typename\n  }\n}\n\nfragment metrcTransferFragment on MetrcTransfer {\n  id\n  orderId\n  order {\n    id\n    metrcWarehouseLicenseNumber\n    __typename\n  }\n  originLicensedLocationId\n  originLicensedLocation {\n    ...licensedLocationFragment\n    __typename\n  }\n  destinationLicensedLocationId\n  destinationLicensedLocation {\n    ...licensedLocationFragment\n    __typename\n  }\n  metrcManifestId\n  metrcTransferTemplateName\n  metrcManifestS3FileLink\n  metrcOrderNotes\n  shipmentId\n  shipment {\n    ...shipmentFragment\n    __typename\n  }\n  creatorId\n  creator {\n    id\n    email\n    __typename\n  }\n  createdAt\n  updatedAt\n  __typename\n}\n\nfragment licensedLocationFragment on LicensedLocation {\n  id\n  name\n  address1\n  address2\n  city\n  state\n  zip\n  siteCategory\n  lat\n  lng\n  billingAddress1\n  billingAddress2\n  billingAddressCity\n  billingAddressState\n  billingAddressZip\n  warehouseId\n  isArchived\n  doingBusinessAs\n  noExciseTax\n  phoneNumber\n  printCoas\n  hoursBusiness\n  hoursDelivery\n  deliveryByApptOnly\n  specialProtocol\n  schedulingSoftwareRequired\n  schedulingSoftwareLink\n  centralizedPurchasingNotes\n  payByCheck\n  collectionNotes\n  deliveryNotes\n  collect1PocFirstName\n  collect1PocLastName\n  collect1PocTitle\n  collect1PocNumber\n  collect1PocEmail\n  collect1PocAllowsText\n  collect1PreferredContactMethod\n  collect2PocFirstName\n  collect2PocLastName\n  collect2PocTitle\n  collect2PocNumber\n  collect2PocEmail\n  collect2PocAllowsText\n  collect2PreferredContactMethod\n  delivery1PocFirstName\n  delivery1PocLastName\n  delivery1PocTitle\n  delivery1PocNumber\n  delivery1PocEmail\n  delivery1PocAllowsText\n  delivery1PreferredContactMethod\n  delivery2PocFirstName\n  delivery2PocLastName\n  delivery2PocTitle\n  delivery2PocNumber\n  delivery2PocEmail\n  delivery2PocAllowsText\n  delivery2PreferredContactMethod\n  unmaskedId\n  qualitativeRating\n  creditRating\n  trustLevelNabis\n  trustLevelInEffect\n  isOnNabisTracker\n  locationNotes\n  infoplus\n  w9Link\n  taxIdentificationNumber\n  sellerPermitLink\n  nabisMaxTerms\n  __typename\n}\n\nfragment shipmentFragment on Shipment {\n  id\n  orderId\n  originLicensedLocationId\n  destinationLicensedLocationId\n  status\n  stagingAreaId\n  isUnloaded\n  unloaderId\n  isLoaded\n  loaderId\n  arrivalTime\n  departureTime\n  isShipped\n  vehicleId\n  driverId\n  previousShipmentId\n  nextShipmentId\n  infoplusOrderId\n  infoplusAsnId\n  infoplusOrderInventoryStatus\n  infoplusAsnInventoryStatus\n  createdAt\n  updatedAt\n  shipmentNumber\n  queueOrder\n  isStaged\n  isPrinted\n  arrivalTimeAfter\n  arrivalTimeBefore\n  fulfillability\n  pickers\n  shipmentType\n  intaken\n  outtaken\n  metrcWarehouseLicenseNumber\n  __typename\n}\n",
            }
        ]
    )
    headers = {
        "authority": "api.getnabis.com",
        "accept": "*/*",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2NDc3MjkwOTQsImlzQWRtaW4iOnRydWUsImlzRHJpdmVyIjpmYWxzZSwiaWF0IjoxNjQ2NDMzMDk0LCJhdWQiOiJhZG1pbiIsImlzcyI6Imh0dHBzOi8vZ2V0bmFiaXMuY29tIiwic3ViIjoiZDI0NDczZDctNzBjZS00N2M4LTg1OTItOWVlY2Q0NzgzMDQ0In0.k5zC5b_LSxLjLMlYVFc-qIKos56PIDvUdutKEHDlMLw",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",
        "content-type": "application/json",
        "sec-gpc": "1",
        "origin": "https://app.getnabis.com",
        "sec-fetch-site": "same-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://app.getnabis.com/",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.text)
