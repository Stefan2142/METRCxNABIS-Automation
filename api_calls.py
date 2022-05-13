import requests, json, time, copy
from tenacity import retry, wait_fixed
from creds import nabis_bearer_token, metrc_bearer_token
from config import nabis_api_url, nabis_headers, WAREHOUSE
from config import paths

SHIPMENTS = []
DATE_FILTER = None


# "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",

metrc_api_base_url = "https://api-ca.metrc.com//"


@retry(wait=wait_fixed(5))
def metrc_get_manifest_pdf(metrc_manifest_id, WAREHOUSE):

    url = f"https://ca.metrc.com/reports/transfers/{WAREHOUSE['license']}/manifest?id={metrc_manifest_id}"

    manifest_headers = {
        "authority": "ca.metrc.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "cache-control": "max-age=0",
        "cookie": "MetrcRequestToken=AOph_zi7ATG-3Pic6_EALxE5hGirmH0aUBlX97jAs2SG_YuE1tQG8eMb8LOPzExAnX95ov0-V0i09cXbtKiKb4eNC2BhjMYdIE5qJDZTStkmo2L8WYw3oErk39fSJ1XI834MBvkUC6RVfwrTCT2KXQ2; MetrcAuth=13CAD0B87DD7C13E0A251AD508CDB08B1CCFB897732B67CFEC79068F9F5BE6E8C4543158A4D59701BB1ACF4D144BFB6613AF1668B3B0BF2028D4E4D8BB4B851DFD4F6EE5DD1CD2B1DE5EF8E78FE80922C13B40BF003C7F07D5BA4D593235863CC7AA101B88E8404B4DBB4FAD62C9E74144390298E097609A149143E07DA96667DCD9607BF5A087D933E3687E2E2E09BAB6259CA47AE8C7533EC6498C5A2E59A0A0D2E9D7F62A271340D724FE197AF940D7441DC71960D415A8239757A8FE565D413CA4CED6322B9CCFE8B57200E201DA9D0B77B032F75091E3956C4B5014BF765952B745DB2F5811F6E36F8D4F9BA6A0FEE0D992E53F3FA07F47BE6480C285F2311E46CD0F4EA1F6296FDBC12C5D6E905175F6016DF7AD05284819A655BA619B30F01A1199A515E3206F0FD9CF21AFFD5C2CF610C298D80E76533E1DBA129829; MetrcSessionTime=2022-05-13T15:25:49Z; MetrcAuth=9D3212FD0C2A0D0ABD88B6F3D991879023F5E6AB27AC09AAA01E7EF9447AAC1C4288431BBC383DEC336EB10A8EA9742841A0682DED31B0F7B10EC498F93F917590DF69F869F538155A6BD61919BB966822AE1DB34E65684A256F75C376DE2CFFD0F8F99136B0D5AC92926D2F724C3D06DF0DD73F6E0827FFC6785D26EF40C2E44AE5DD8866243A638DE15C03C01BED806061F9918F920525EB07931698087E2AEDA002B19BBBBCD0DAC74D08C71D8B5C6F90081A6BFA5965DFFC2B2ED7C8B8D5EB2C0F0CC69BA495438BDED584741EFB3AC6B4822DCD8D16311F3F4131C7150AC9B9072BBA0C043B86E88814B3D35ECEBC7A23405C0F3B0D8FDD0D635B5F3449F20C5B878284E7C3666387DD4CCE88C4F91A8A964829008178BDF0E559DA9B2ED7C1DDDD121F45FFE92A227548FE2149397818E9F15559404290E8449892787D; MetrcSessionTime=2022-05-13T15:26:28Z",
        "referer": f"https://ca.metrc.com/industry/{WAREHOUSE['license']}/transfers/licensed",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "sec-gpc": "1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36",
    }
    # https://stackoverflow.com/questions/21746750/check-and-wait-until-a-file-exists-to-read-it
    response = requests.request("GET", url, headers=manifest_headers)
    with open(f"./{paths['pdfs']}/{metrc_manifest_id}", "wb") as f:
        f.write(response.content)


@retry(wait=wait_fixed(5))
def metrc_api_get_templates():
    """Get list of available templates for a given WAREHOUSE license

    Returns:
        dict: list of dicts (json like structure) where each element contains template data
    """
    url = (
        metrc_api_base_url
        + f"transfers/v1/templates?licenseNumber={WAREHOUSE['license']}"
    )
    headers = {"Authorization": metrc_bearer_token}
    response = requests.request("GET", url, headers=headers)
    return response.json()


@retry(wait=wait_fixed(5))
def metrc_api_get_template_deliveries(template_id):
    url = metrc_api_base_url + f"transfers/v1/templates/{template_id}/deliveries"
    headers = {"Authorization": metrc_bearer_token}
    response = requests.request("GET", url, headers=headers)
    return response.json()


@retry(wait=wait_fixed(5))
def metrc_api_get_template_packages(template_id):
    url = metrc_api_base_url + f"transfers/v1/templates/delivery/{template_id}/packages"
    headers = {"Authorization": metrc_bearer_token}
    response = requests.request("GET", url, headers=headers)
    response.json()
    return response.json()


@retry(wait=wait_fixed(5))
def metrc_api_find_template(order_id):
    url = (
        metrc_api_base_url
        + f"transfers/v1/templates?licenseNumber={WAREHOUSE['license']}"
    )

    headers = {"Authorization": metrc_bearer_token}

    response = requests.request("GET", url, headers=headers)

    templates = response.json()
    for template in templates:
        if str(order_id) in template["Name"]:
            print(template)
            return template
    return False


def metrc_api_archive_template(template_id):
    url = (
        metrc_api_base_url
        + f"transfers/v1/templates/{template_id}?licenseNumber={WAREHOUSE['license']}"
    )

    headers = {"Authorization": metrc_bearer_token}

    response = requests.request("DELETE", url, headers=headers)

    return response


@retry(wait=wait_fixed(5))
def create_manifest(api_token, cookie, metrc_lic, payload):

    url = "https://ca.metrc.com/api/transfers/create"

    headers = {
        "ApiVerificationToken": api_token,
        "X-Metrc-LicenseNumber": metrc_lic,
        "sec-ch-ua-mobile": "?0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://ca.metrc.com",
        "Cookie": cookie,
    }
    response = requests.request("POST", url, headers=headers, data=payload)

    return response.json()


@retry(wait=wait_fixed(5))
def find_template(order_id, api_token, cookie, metrc_lic):

    url = "https://ca.metrc.com/api/transfers/templates?slt=Licensed"

    payload = json.dumps(
        {
            "request": {
                "take": 20,
                "skip": 0,
                "page": 1,
                "pageSize": 20,
                "filter": {
                    "logic": "and",
                    "filters": [
                        {
                            "field": "Name",
                            "operator": "contains",
                            "value": str(order_id),
                        }
                    ],
                },
                "group": [],
            }
        }
    )
    headers = {
        "ApiVerificationToken": api_token,
        "X-Metrc-LicenseNumber": metrc_lic,
        "sec-ch-ua-mobile": "?0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://ca.metrc.com",
        "Cookie": cookie,
    }
    response = requests.request("POST", url, headers=headers, data=payload)

    time.sleep(3)
    # print(response.text)
    return response.json()


def get_nabis_drivers():

    payload = json.dumps(
        [
            {
                "operationName": "AllDrivers",
                "variables": {"input": {}},
                "query": "query AllDrivers {\n  viewer {\n    allDrivers {\n      ...driverFragment\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment driverFragment on Driver {\n  id\n  firstName\n  lastName\n  driversLicense\n  email\n  isArchived\n  __typename\n}\n",
            },
            {
                "operationName": "AllDrivers",
                "variables": {},
                "query": "query AllDrivers {\n  viewer {\n    allDrivers {\n      ...driverFragment\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment driverFragment on Driver {\n  id\n  firstName\n  lastName\n  driversLicense\n  email\n  isArchived\n  __typename\n}\n",
            },
        ]
    )

    response = requests.request(
        "POST", nabis_api_url, headers=nabis_headers, data=payload
    )
    response = response.json()
    return response


def get_nabis_vehicles():

    payload = json.dumps(
        [
            {
                "operationName": "AllVehicles",
                "variables": {},
                "query": "query AllVehicles {\n  viewer {\n    allVehicles {\n      ...vehicleFragment\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment vehicleFragment on Vehicle {\n  id\n  name\n  make\n  model\n  licensePlate\n  year\n  __typename\n}\n",
            },
            {
                "operationName": "AllVehicles",
                "variables": {"input": {}},
                "query": "query AllVehicles {\n  viewer {\n    allVehicles {\n      ...vehicleFragment\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment vehicleFragment on Vehicle {\n  id\n  name\n  make\n  model\n  licensePlate\n  year\n  __typename\n}\n",
            },
            {
                "operationName": "AllDrivers",
                "variables": {"input": {}},
                "query": "query AllDrivers {\n  viewer {\n    allDrivers {\n      ...driverFragment\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment driverFragment on Driver {\n  id\n  firstName\n  lastName\n  driversLicense\n  email\n  isArchived\n  __typename\n}\n",
            },
        ]
    )
    response = requests.request(
        "POST", nabis_api_url, headers=nabis_headers, data=payload
    )
    if response.status_code == 502:
        time.sleep(1)
        response = requests.request(
            "POST", nabis_api_url, headers=nabis_headers, data=payload
        )
    response = response.json()
    return response


@retry(wait=wait_fixed(2))
def upload_order_note(transfer_id, order_note):

    payload = json.dumps(
        [
            {
                "operationName": "updateMetrcTransfer",
                "variables": {
                    "id": transfer_id,
                    "metrcOrderNotes": order_note,
                },
                "query": "mutation updateMetrcTransfer($id: ID!, $metrcManifestId: Int, $metrcTransferTemplateName: String, $metrcManifestS3FileLink: String, $metrcOrderNotes: String, $metrcManifestFile: Upload) {\n  updateMetrcTransfer(id: $id, metrcManifestId: $metrcManifestId, metrcTransferTemplateName: $metrcTransferTemplateName, metrcManifestS3FileLink: $metrcManifestS3FileLink, metrcOrderNotes: $metrcOrderNotes, metrcManifestFile: $metrcManifestFile) {\n    ...metrcTransferFragment\n    __typename\n  }\n}\n\nfragment metrcTransferFragment on MetrcTransfer {\n  id\n  orderId\n  order {\n    id\n    metrcWarehouseLicenseNumber\n    __typename\n  }\n  originLicensedLocationId\n  originLicensedLocation {\n    ...licensedLocationFragment\n    __typename\n  }\n  destinationLicensedLocationId\n  destinationLicensedLocation {\n    ...licensedLocationFragment\n    __typename\n  }\n  metrcManifestId\n  metrcTransferTemplateName\n  metrcManifestS3FileLink\n  metrcOrderNotes\n  shipmentId\n  shipment {\n    ...shipmentFragment\n    __typename\n  }\n  creatorId\n  creator {\n    id\n    email\n    __typename\n  }\n  createdAt\n  updatedAt\n  __typename\n}\n\nfragment licensedLocationFragment on LicensedLocation {\n  id\n  name\n  address1\n  address2\n  city\n  state\n  zip\n  siteCategory\n  lat\n  lng\n  billingAddress1\n  billingAddress2\n  billingAddressCity\n  billingAddressState\n  billingAddressZip\n  warehouseId\n  isArchived\n  doingBusinessAs\n  noExciseTax\n  phoneNumber\n  printCoas\n  hoursBusiness\n  hoursDelivery\n  deliveryByApptOnly\n  specialProtocol\n  schedulingSoftwareRequired\n  schedulingSoftwareLink\n  centralizedPurchasingNotes\n  payByCheck\n  collectionNotes\n  deliveryNotes\n  collect1PocFirstName\n  collect1PocLastName\n  collect1PocTitle\n  collect1PocNumber\n  collect1PocEmail\n  collect1PocAllowsText\n  collect1PreferredContactMethod\n  collect2PocFirstName\n  collect2PocLastName\n  collect2PocTitle\n  collect2PocNumber\n  collect2PocEmail\n  collect2PocAllowsText\n  collect2PreferredContactMethod\n  delivery1PocFirstName\n  delivery1PocLastName\n  delivery1PocTitle\n  delivery1PocNumber\n  delivery1PocEmail\n  delivery1PocAllowsText\n  delivery1PreferredContactMethod\n  delivery2PocFirstName\n  delivery2PocLastName\n  delivery2PocTitle\n  delivery2PocNumber\n  delivery2PocEmail\n  delivery2PocAllowsText\n  delivery2PreferredContactMethod\n  unmaskedId\n  qualitativeRating\n  creditRating\n  trustLevelNabis\n  trustLevelInEffect\n  isOnNabisTracker\n  locationNotes\n  infoplus\n  w9Link\n  taxIdentificationNumber\n  sellerPermitLink\n  nabisMaxTerms\n  __typename\n}\n\nfragment shipmentFragment on Shipment {\n  id\n  orderId\n  originLicensedLocationId\n  destinationLicensedLocationId\n  status\n  stagingAreaId\n  isUnloaded\n  unloaderId\n  isLoaded\n  loaderId\n  arrivalTime\n  departureTime\n  isShipped\n  vehicleId\n  driverId\n  previousShipmentId\n  nextShipmentId\n  infoplusOrderId\n  infoplusAsnId\n  infoplusOrderInventoryStatus\n  infoplusAsnInventoryStatus\n  createdAt\n  updatedAt\n  shipmentNumber\n  queueOrder\n  isStaged\n  isPrinted\n  arrivalTimeAfter\n  arrivalTimeBefore\n  fulfillability\n  pickers\n  shipmentType\n  intaken\n  outtaken\n  metrcWarehouseLicenseNumber\n  __typename\n}\n",
            }
        ]
    )

    custom_header = copy.deepcopy(nabis_headers)
    custom_header.update(
        {
            "sec-gpc": "1",
            "origin": "https://app.getnabis.com",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://app.getnabis.com/",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        }
    )

    response = requests.request(
        "POST", nabis_api_url, headers=nabis_headers, data=payload
    )
    try:
        return response.json()
    except:
        return False


@retry(wait=wait_fixed(5))
def upload_manifest_id(transfer_id, manifest_id):
    # try:
    #     del pdf_header["content-type"]
    # except:
    #     pass
    custom_header = copy.deepcopy(nabis_headers)
    custom_header.update(
        {
            "sec-gpc": "1",
            "origin": "https://app.getnabis.com",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://app.getnabis.com/",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        }
    )

    payload = json.dumps(
        [
            {
                "operationName": "updateMetrcTransfer",
                "variables": {
                    "id": transfer_id,
                    "metrcManifestId": int(manifest_id),
                },
                "query": "mutation updateMetrcTransfer($id: ID!, $metrcManifestId: Int, $metrcTransferTemplateName: String, $metrcManifestS3FileLink: String, $metrcOrderNotes: String, $metrcManifestFile: Upload) {\n  updateMetrcTransfer(id: $id, metrcManifestId: $metrcManifestId, metrcTransferTemplateName: $metrcTransferTemplateName, metrcManifestS3FileLink: $metrcManifestS3FileLink, metrcOrderNotes: $metrcOrderNotes, metrcManifestFile: $metrcManifestFile) {\n    ...metrcTransferFragment\n    __typename\n  }\n}\n\nfragment metrcTransferFragment on MetrcTransfer {\n  id\n  orderId\n  order {\n    id\n    metrcWarehouseLicenseNumber\n    __typename\n  }\n  originLicensedLocationId\n  originLicensedLocation {\n    ...licensedLocationFragment\n    __typename\n  }\n  destinationLicensedLocationId\n  destinationLicensedLocation {\n    ...licensedLocationFragment\n    __typename\n  }\n  metrcManifestId\n  metrcTransferTemplateName\n  metrcManifestS3FileLink\n  metrcOrderNotes\n  shipmentId\n  shipment {\n    ...shipmentFragment\n    __typename\n  }\n  creatorId\n  creator {\n    id\n    email\n    __typename\n  }\n  createdAt\n  updatedAt\n  __typename\n}\n\nfragment licensedLocationFragment on LicensedLocation {\n  id\n  name\n  address1\n  address2\n  city\n  state\n  zip\n  siteCategory\n  lat\n  lng\n  billingAddress1\n  billingAddress2\n  billingAddressCity\n  billingAddressState\n  billingAddressZip\n  warehouseId\n  isArchived\n  doingBusinessAs\n  noExciseTax\n  phoneNumber\n  printCoas\n  hoursBusiness\n  hoursDelivery\n  deliveryByApptOnly\n  specialProtocol\n  schedulingSoftwareRequired\n  schedulingSoftwareLink\n  centralizedPurchasingNotes\n  payByCheck\n  collectionNotes\n  deliveryNotes\n  collect1PocFirstName\n  collect1PocLastName\n  collect1PocTitle\n  collect1PocNumber\n  collect1PocEmail\n  collect1PocAllowsText\n  collect1PreferredContactMethod\n  collect2PocFirstName\n  collect2PocLastName\n  collect2PocTitle\n  collect2PocNumber\n  collect2PocEmail\n  collect2PocAllowsText\n  collect2PreferredContactMethod\n  delivery1PocFirstName\n  delivery1PocLastName\n  delivery1PocTitle\n  delivery1PocNumber\n  delivery1PocEmail\n  delivery1PocAllowsText\n  delivery1PreferredContactMethod\n  delivery2PocFirstName\n  delivery2PocLastName\n  delivery2PocTitle\n  delivery2PocNumber\n  delivery2PocEmail\n  delivery2PocAllowsText\n  delivery2PreferredContactMethod\n  unmaskedId\n  qualitativeRating\n  creditRating\n  trustLevelNabis\n  trustLevelInEffect\n  isOnNabisTracker\n  locationNotes\n  infoplus\n  w9Link\n  taxIdentificationNumber\n  sellerPermitLink\n  nabisMaxTerms\n  __typename\n}\n\nfragment shipmentFragment on Shipment {\n  id\n  orderId\n  originLicensedLocationId\n  destinationLicensedLocationId\n  status\n  stagingAreaId\n  isUnloaded\n  unloaderId\n  isLoaded\n  loaderId\n  arrivalTime\n  departureTime\n  isShipped\n  vehicleId\n  driverId\n  previousShipmentId\n  nextShipmentId\n  infoplusOrderId\n  infoplusAsnId\n  infoplusOrderInventoryStatus\n  infoplusAsnInventoryStatus\n  createdAt\n  updatedAt\n  shipmentNumber\n  queueOrder\n  isStaged\n  isPrinted\n  arrivalTimeAfter\n  arrivalTimeBefore\n  fulfillability\n  pickers\n  shipmentType\n  intaken\n  outtaken\n  metrcWarehouseLicenseNumber\n  __typename\n}\n",
            }
        ]
    )

    response = requests.request(
        "POST", nabis_api_url, headers=nabis_headers, data=payload
    )
    try:
        return response.json()
    except:
        return False


@retry(wait=wait_fixed(5))
def upload_manifest_pdf(transfer_id, pdf_fl):
    global nabis_bearer_token
    pdf_header = {
        "authority": "api.getnabis.com",
        "accept": "*/*",
        "authorization": nabis_bearer_token,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
    }

    payload = {
        "operations": '{"operationName":"updateMetrcTransfer","variables":{"id":"%s","metrcManifestFile":null},"query":"mutation updateMetrcTransfer($id: ID!, $metrcManifestId: Int, $metrcTransferTemplateName: String, $metrcManifestS3FileLink: String, $metrcOrderNotes: String, $metrcManifestFile: Upload) {\\n  updateMetrcTransfer(id: $id, metrcManifestId: $metrcManifestId, metrcTransferTemplateName: $metrcTransferTemplateName, metrcManifestS3FileLink: $metrcManifestS3FileLink, metrcOrderNotes: $metrcOrderNotes, metrcManifestFile: $metrcManifestFile) {\\n    ...metrcTransferFragment\\n    __typename\\n  }\\n}\\n\\nfragment metrcTransferFragment on MetrcTransfer {\\n  id\\n  orderId\\n  order {\\n    id\\n    metrcWarehouseLicenseNumber\\n    __typename\\n  }\\n  originLicensedLocationId\\n  originLicensedLocation {\\n    ...licensedLocationFragment\\n    __typename\\n  }\\n  destinationLicensedLocationId\\n  destinationLicensedLocation {\\n    ...licensedLocationFragment\\n    __typename\\n  }\\n  metrcManifestId\\n  metrcTransferTemplateName\\n  metrcManifestS3FileLink\\n  metrcOrderNotes\\n  shipmentId\\n  shipment {\\n    ...shipmentFragment\\n    __typename\\n  }\\n  creatorId\\n  creator {\\n    id\\n    email\\n    __typename\\n  }\\n  createdAt\\n  updatedAt\\n  __typename\\n}\\n\\nfragment licensedLocationFragment on LicensedLocation {\\n  id\\n  name\\n  address1\\n  address2\\n  city\\n  state\\n  zip\\n  siteCategory\\n  lat\\n  lng\\n  billingAddress1\\n  billingAddress2\\n  billingAddressCity\\n  billingAddressState\\n  billingAddressZip\\n  warehouseId\\n  isArchived\\n  doingBusinessAs\\n  noExciseTax\\n  phoneNumber\\n  printCoas\\n  hoursBusiness\\n  hoursDelivery\\n  deliveryByApptOnly\\n  specialProtocol\\n  schedulingSoftwareRequired\\n  schedulingSoftwareLink\\n  centralizedPurchasingNotes\\n  payByCheck\\n  collectionNotes\\n  deliveryNotes\\n  collect1PocFirstName\\n  collect1PocLastName\\n  collect1PocTitle\\n  collect1PocNumber\\n  collect1PocEmail\\n  collect1PocAllowsText\\n  collect1PreferredContactMethod\\n  collect2PocFirstName\\n  collect2PocLastName\\n  collect2PocTitle\\n  collect2PocNumber\\n  collect2PocEmail\\n  collect2PocAllowsText\\n  collect2PreferredContactMethod\\n  delivery1PocFirstName\\n  delivery1PocLastName\\n  delivery1PocTitle\\n  delivery1PocNumber\\n  delivery1PocEmail\\n  delivery1PocAllowsText\\n  delivery1PreferredContactMethod\\n  delivery2PocFirstName\\n  delivery2PocLastName\\n  delivery2PocTitle\\n  delivery2PocNumber\\n  delivery2PocEmail\\n  delivery2PocAllowsText\\n  delivery2PreferredContactMethod\\n  unmaskedId\\n  qualitativeRating\\n  creditRating\\n  trustLevelNabis\\n  trustLevelInEffect\\n  isOnNabisTracker\\n  locationNotes\\n  infoplus\\n  w9Link\\n  taxIdentificationNumber\\n  sellerPermitLink\\n  nabisMaxTerms\\n  __typename\\n}\\n\\nfragment shipmentFragment on Shipment {\\n  id\\n  orderId\\n  originLicensedLocationId\\n  destinationLicensedLocationId\\n  status\\n  stagingAreaId\\n  isUnloaded\\n  unloaderId\\n  isLoaded\\n  loaderId\\n  arrivalTime\\n  departureTime\\n  isShipped\\n  vehicleId\\n  driverId\\n  previousShipmentId\\n  nextShipmentId\\n  infoplusOrderId\\n  infoplusAsnId\\n  infoplusOrderInventoryStatus\\n  infoplusAsnInventoryStatus\\n  createdAt\\n  updatedAt\\n  shipmentNumber\\n  queueOrder\\n  isStaged\\n  isPrinted\\n  arrivalTimeAfter\\n  arrivalTimeBefore\\n  fulfillability\\n  pickers\\n  shipmentType\\n  intaken\\n  outtaken\\n  metrcWarehouseLicenseNumber\\n  __typename\\n}\\n"}'
        % transfer_id,
        "map": '{"1":["variables.metrcManifestFile"]}',
    }
    files = [
        (
            "1",
            (
                pdf_fl,
                open(pdf_fl, "rb"),
                "application/octet-stream",
            ),
        )
    ]

    response = requests.request(
        "POST", nabis_api_url, headers=pdf_header, data=payload, files=files
    )

    try:
        return response.json()
    except json.decoder.JSONDecodeError:
        return False


@retry(wait=wait_fixed(5))
def get_metrc_order_and_all_metrc_resources(order_id):
    payload = json.dumps(
        [
            {
                "operationName": "getMetrcOrderAndAllMetrcResources",
                "variables": {"orderId": order_id},
                "query": "query getMetrcOrderAndAllMetrcResources($orderId: ID!) {\n  viewer {\n    getOnlyMetrcOrder(orderId: $orderId) {\n      details\n      errors {\n        type\n        message\n        __typename\n      }\n      warnings {\n        type\n        message\n        __typename\n      }\n      licenseNumber\n      lineItems {\n        id\n        __typename\n      }\n      tagSequence\n      warehouseKey\n      __typename\n    }\n    getMetrcItems(orderId: $orderId)\n    __typename\n  }\n}\n",
            }
        ]
    )

    response = requests.request(
        "POST", nabis_api_url, headers=nabis_headers, data=payload
    )
    time.sleep(1)
    return response.json()


@retry(wait=wait_fixed(5))
def get_order_data(order_number):

    payload = json.dumps(
        {
            "operationName": "GetOrder",
            "query": "\n  query GetOrder($id: ID, $orderNumber: Int, $sortLikeMetrc: Boolean) {\n    getOrder(id: $id, orderNumber: $orderNumber) {\n      id\n      siteLicenseNum\n      date\n      invoicesS3FileLink\n      action\n      status\n      name\n      irn\n      referrer\n      isSampleDemo\n      notes\n      adminNotes\n      brandManifestNotes\n      nabisManifestNotes\n      retailerManifestNotes\n      driver {\n        id\n        firstName\n        lastName\n        driversLicense\n      }\n      vehicle {\n        id\n        name\n        make\n        model\n        year\n        licensePlate\n      }\n      site {\n        id\n        licensedLocation {\n          id\n          name\n          doingBusinessAs\n          address1\n          address2\n          city\n          state\n          zip\n          licenses {\n            id\n            nickname\n            legalEntityName\n            licenseNumber\n            issuanceDate\n            expirationDate\n          }\n        }\n      }\n      lineItems(sortLikeMetrc: $sortLikeMetrc) {\n        id\n        quantity\n        discount\n        pricePerUnit\n        metrcPackageTag\n        taggedAt\n        lineItemManifestNotes\n        isSample\n        skuBatch {\n          id\n          batch {\n            id\n            code\n          }\n          sku {\n            id\n            name\n            code\n            organization {\n              id\n            }\n          }\n        }\n      }\n      warehouse {\n        id\n        license {\n          id\n          nickname\n          legalEntityName\n          licenseNumber\n          issuanceDate\n          expirationDate\n        }\n        site {\n          id\n          name\n          address1\n          address2\n          city\n          state\n          zip\n        }\n      }\n      organization {\n        id\n        name\n        doingBusinessAs\n      }\n    }\n  }\n",
            "variables": {"orderNumber": int(order_number), "sortLikeMetrc": True},
        }
    )

    response = requests.request(
        "POST", nabis_api_url, headers=nabis_headers, data=payload
    )
    time.sleep(1)
    response = response.json()
    return response["data"]["getOrder"]


@retry(wait=wait_fixed(5))
def view_metrc_transfer(order_id):
    payload = json.dumps(
        {
            "operationName": "getMetrcTransfers",
            "variables": {"orderId": str(order_id)},
            "query": "query getMetrcTransfers($orderId: ID!) {\n  getMetrcTransfers(orderId: $orderId) {\n    ...metrcTransferFragment\n    __typename\n  }\n}\n\nfragment metrcTransferFragment on MetrcTransfer {\n  id\n  orderId\n  order {\n    id\n    metrcWarehouseLicenseNumber\n    __typename\n  }\n  originLicensedLocationId\n  originLicensedLocation {\n    ...licensedLocationFragment\n    __typename\n  }\n  destinationLicensedLocationId\n  destinationLicensedLocation {\n    ...licensedLocationFragment\n    __typename\n  }\n  metrcManifestId\n  metrcTransferTemplateName\n  metrcManifestS3FileLink\n  metrcOrderNotes\n  shipmentId\n  shipment {\n    ...shipmentFragment\n    __typename\n  }\n  creatorId\n  creator {\n    id\n    email\n    __typename\n  }\n  createdAt\n  updatedAt\n  __typename\n}\n\nfragment licensedLocationFragment on LicensedLocation {\n  id\n  name\n  address1\n  address2\n  city\n  state\n  zip\n  siteCategory\n  lat\n  lng\n  billingAddress1\n  billingAddress2\n  billingAddressCity\n  billingAddressState\n  billingAddressZip\n  warehouseId\n  isArchived\n  doingBusinessAs\n  noExciseTax\n  phoneNumber\n  printCoas\n  hoursBusiness\n  hoursDelivery\n  deliveryByApptOnly\n  specialProtocol\n  schedulingSoftwareRequired\n  schedulingSoftwareLink\n  centralizedPurchasingNotes\n  payByCheck\n  collectionNotes\n  deliveryNotes\n  collect1PocFirstName\n  collect1PocLastName\n  collect1PocTitle\n  collect1PocNumber\n  collect1PocEmail\n  collect1PocAllowsText\n  collect1PreferredContactMethod\n  collect2PocFirstName\n  collect2PocLastName\n  collect2PocTitle\n  collect2PocNumber\n  collect2PocEmail\n  collect2PocAllowsText\n  collect2PreferredContactMethod\n  delivery1PocFirstName\n  delivery1PocLastName\n  delivery1PocTitle\n  delivery1PocNumber\n  delivery1PocEmail\n  delivery1PocAllowsText\n  delivery1PreferredContactMethod\n  delivery2PocFirstName\n  delivery2PocLastName\n  delivery2PocTitle\n  delivery2PocNumber\n  delivery2PocEmail\n  delivery2PocAllowsText\n  delivery2PreferredContactMethod\n  unmaskedId\n  qualitativeRating\n  creditRating\n  trustLevelNabis\n  trustLevelInEffect\n  isOnNabisTracker\n  locationNotes\n  infoplus\n  w9Link\n  taxIdentificationNumber\n  sellerPermitLink\n  nabisMaxTerms\n  __typename\n}\n\nfragment shipmentFragment on Shipment {\n  id\n  orderId\n  originLicensedLocationId\n  destinationLicensedLocationId\n  status\n  stagingAreaId\n  isUnloaded\n  unloaderId\n  isLoaded\n  loaderId\n  arrivalTime\n  departureTime\n  isShipped\n  vehicleId\n  driverId\n  previousShipmentId\n  nextShipmentId\n  infoplusOrderId\n  infoplusAsnId\n  infoplusOrderInventoryStatus\n  infoplusAsnInventoryStatus\n  createdAt\n  updatedAt\n  shipmentNumber\n  queueOrder\n  isStaged\n  isPrinted\n  arrivalTimeAfter\n  arrivalTimeBefore\n  fulfillability\n  pickers\n  shipmentType\n  intaken\n  outtaken\n  metrcWarehouseLicenseNumber\n  __typename\n}\n",
        },
    )
    # Ir will return html code on error instead of json
    response = requests.request(
        "POST", nabis_api_url, headers=nabis_headers, data=payload
    )
    time.sleep(1)
    # print("Couldnt get metrc transfers from nabis site. Restart the script.")
    return response.json()

    #                                  | -> this is a list of how many transfer templates there are
    # We can use directly this template name to search it on the metrc site


@retry(wait=wait_fixed(5))
def get_tracker_shipments(tomorrow, page=1):

    # origin - its the NABIS LA origin field
    # metrcStatus - set to COMPLETE
    # departureTime - desired date
    payload = json.dumps(
        [
            {
                "operationName": "getTrackerShipments",
                "variables": {
                    "ShipmentTrackerQueryInput": {
                        "departureTimeStart": tomorrow,
                        "origin": [WAREHOUSE["id"]],
                        "metrcStatus": ["COMPLETE"],
                        "orderStatus": ["SCHEDULED", "TRANSFERRING", "UNSCHEDULED"],
                        "metrcManifestCreated": False,
                        "pageInfo": {
                            "numItemsPerPage": 25,
                            "orderBy": [
                                {"attribute": "departureTime", "order": "DESC"},
                                {"attribute": "createdAt", "order": "DESC"},
                            ],
                            "page": page,
                        },
                        "includeStatistics": True,
                    }
                },
                "query": "query getTrackerShipments($ShipmentTrackerQueryInput: ShipmentTrackerQueryInput!) {\n  getTrackerShipments(input: $ShipmentTrackerQueryInput) {\n    pageInfo {\n      page\n      numItemsPerPage\n      orderBy {\n        attribute\n        order\n        __typename\n      }\n      totalNumItems\n      totalNumPages\n      __typename\n    }\n    results {\n      id\n      updatedAt\n      shipmentNumber\n      orderId\n      orderAction\n      orderStatus\n      orderNumber\n      order {\n        id\n        number\n        lastNonReturnShipmentId\n        packingListS3FileLink\n        invoicesS3FileLink\n        apSummaryS3FileLink\n        apSummaryGDriveFileId\n        qrcodeS3FileLink\n        metrcWarehouseLicenseNumber\n        lineItems {\n          skuBatch {\n            batch {\n              manifestGDriveFileId\n              coaS3FileLink\n              __typename\n            }\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      infoplusOrderId\n      infoplusAsnId\n      infoplusOrderInventoryStatus\n      infoplusAsnInventoryStatus\n      fulfillability\n      status\n      organization {\n        ...organizationFragment\n        __typename\n      }\n      destinationLicensedLocation {\n        ...licensedLocationFragment\n        __typename\n      }\n      originLicensedLocation {\n        ...licensedLocationFragment\n        __typename\n      }\n      confirmationName\n      confirmationNotes\n      confirmationStatus\n      confirmationTrail\n      departureTime\n      vehicleId\n      driverId\n      onFleetUpdatedAt\n      isStaged\n      stagingAreaId\n      metrcTagSequences {\n        value\n        inclusive\n        __typename\n      }\n      metrcOrderStatus\n      metrcOrderNotes\n      metrcOrderAssociate\n      metrcTransferId\n      metrcTransferNotes\n      metrcTransferManifestId\n      queueOrder\n      arrivalTime\n      arrivalTimeAfter\n      arrivalTimeBefore\n      isPrinted\n      pickers\n      intaken\n      outtaken\n      metrcWarehouseLicenseNumber\n      __typename\n    }\n    statistics {\n      numberPicked\n      numberShipped\n      numberStaged\n      numberOnOrder\n      numberFulfilled\n      numberMetrcTagsCompleted\n      numberMetrcStatusCompleted\n      numberMetrcManifestSaved\n      totalShipments\n      totalShipmentsLinkedToInfoplus\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment organizationFragment on Organization {\n  id\n  address1\n  address2\n  alias\n  city\n  doingBusinessAs\n  factoredStatus\n  hasAnalyticsDashboard\n  infoplus\n  isBrand\n  isManufacturer\n  isRetailer\n  isSalesOrg\n  isMarketplace\n  licensedLocationId\n  logoS3Link\n  manifestGDriveFolderId\n  marketplaceContactEmail\n  marketplaceContactName\n  marketplaceContactNumber\n  name\n  phone\n  receiveReports\n  singleHubWarehouseId\n  singleHubWarehouse {\n    ...allWarehousesFragment\n    __typename\n  }\n  state\n  type\n  zip\n  __typename\n}\n\nfragment allWarehousesFragment on Warehouse {\n  ...warehouseFragment\n  site {\n    ...siteFragment\n    licenses {\n      ...licenseFragment\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment warehouseFragment on Warehouse {\n  id\n  isArchived\n  infoplus\n  region\n  isInUseByOps\n  isSingleHub\n  __typename\n}\n\nfragment siteFragment on Site {\n  id\n  name\n  address1\n  address2\n  city\n  state\n  zip\n  pocName\n  pocPhoneNumber\n  pocEmail\n  siteCategory\n  createdAt\n  licensedLocationId\n  __typename\n}\n\nfragment licenseFragment on License {\n  id\n  nickname\n  category\n  type\n  licenseNumber\n  legalEntityName\n  issuanceDate\n  expirationDate\n  contactName\n  contactPhone\n  contactEmail\n  address1\n  address2\n  city\n  state\n  zip\n  archivedAt\n  onboardedAt\n  __typename\n}\n\nfragment licensedLocationFragment on LicensedLocation {\n  id\n  name\n  address1\n  address2\n  city\n  state\n  zip\n  siteCategory\n  lat\n  lng\n  billingAddress1\n  billingAddress2\n  billingAddressCity\n  billingAddressState\n  billingAddressZip\n  warehouseId\n  isArchived\n  doingBusinessAs\n  noExciseTax\n  phoneNumber\n  printCoas\n  hoursBusiness\n  hoursDelivery\n  deliveryByApptOnly\n  specialProtocol\n  schedulingSoftwareRequired\n  schedulingSoftwareLink\n  centralizedPurchasingNotes\n  payByCheck\n  collectionNotes\n  deliveryNotes\n  collect1PocFirstName\n  collect1PocLastName\n  collect1PocTitle\n  collect1PocNumber\n  collect1PocEmail\n  collect1PocAllowsText\n  collect1PreferredContactMethod\n  collect2PocFirstName\n  collect2PocLastName\n  collect2PocTitle\n  collect2PocNumber\n  collect2PocEmail\n  collect2PocAllowsText\n  collect2PreferredContactMethod\n  delivery1PocFirstName\n  delivery1PocLastName\n  delivery1PocTitle\n  delivery1PocNumber\n  delivery1PocEmail\n  delivery1PocAllowsText\n  delivery1PreferredContactMethod\n  delivery2PocFirstName\n  delivery2PocLastName\n  delivery2PocTitle\n  delivery2PocNumber\n  delivery2PocEmail\n  delivery2PocAllowsText\n  delivery2PreferredContactMethod\n  unmaskedId\n  qualitativeRating\n  creditRating\n  trustLevelNabis\n  trustLevelInEffect\n  isOnNabisTracker\n  locationNotes\n  infoplus\n  w9Link\n  taxIdentificationNumber\n  sellerPermitLink\n  nabisMaxTerms\n  __typename\n}\n",
            }
        ]
    )

    response = requests.request(
        "POST", nabis_api_url, headers=nabis_headers, data=payload
    )

    time.sleep(3)
    response.json()
    json_res = response.json()

    if "errors" in json_res[0]:
        print("Couldnt get any shipment result from Nabis, exiting.")
        print(json.dumps(json_res[0], indent=2))

        # response.json()[0]['errors'][0]['message']

        return False
    total_nbr_of_resulting_orders = json_res[0]["data"]["getTrackerShipments"][
        "pageInfo"
    ]["totalNumItems"]
    nbr_of_pages = json_res[0]["data"]["getTrackerShipments"]["pageInfo"][
        "totalNumPages"
    ]
    if page == 1:
        print(
            f"Total shipment search result-set {total_nbr_of_resulting_orders}, pages: {nbr_of_pages}"
        )
    for order in json_res[0]["data"]["getTrackerShipments"]["results"]:
        SHIPMENTS.append(order)

    DATE_FILTER = tomorrow

    if nbr_of_pages > page:
        get_tracker_shipments(DATE_FILTER, page + 1)

    # res[0]["data"]["getTrackerShipments"]
    # res[0]["data"]["getTrackerShipments"]["pageInfo"]
    # res[0]["data"]["getTrackerShipments"]["pageInfo"][
    #     "numItemsPerPage"
    # ]  # search results per page
    # res[0]["data"]["getTrackerShipments"]["pageInfo"][
    #     "totalNumItems"
    # ]  # overal search results
    # res[0]["data"]["getTrackerShipments"]["pageInfo"][
    #     "totalNumPages"
    # ]  # overal number of pages for the search result

    # res[0]["data"]["getTrackerShipments"][
    #     "results"
    # ]  # this is a list of orders in the search result
    return {
        "orders": SHIPMENTS,
        "total_num_pages": nbr_of_pages,
        "total_num_items": total_nbr_of_resulting_orders,
    }
