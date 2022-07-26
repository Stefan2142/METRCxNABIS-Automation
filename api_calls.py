import requests, json, time, copy
from tenacity import retry, wait_fixed
from creds import nabis_bearer_token, metrc_bearer_token
from config import nabis_api_url, nabis_headers, WAREHOUSE
from config import paths

SHIPMENTS = []
DATE_FILTER = None


# "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",

METRC_API_BASE_URL = "https://api-ca.metrc.com//"


@retry(wait=wait_fixed(5))
def metrc_api_get_template_deliveries(template_id):
    url = METRC_API_BASE_URL + f"transfers/v1/templates/{template_id}/deliveries"
    headers = {"Authorization": metrc_bearer_token}
    response = requests.request("GET", url, headers=headers)
    return response.json()


@retry(wait=wait_fixed(5))
def metrc_api_get_template_packages(template_id):
    url = METRC_API_BASE_URL + f"transfers/v1/templates/delivery/{template_id}/packages"
    headers = {"Authorization": metrc_bearer_token}
    response = requests.request("GET", url, headers=headers)
    response.json()
    return response.json()


@retry(wait=wait_fixed(5))
def metrc_api_find_template():
    url = (
        METRC_API_BASE_URL
        + f"transfers/v1/templates?licenseNumber={WAREHOUSE['license']}"
    )

    headers = {"Authorization": metrc_bearer_token}

    response = requests.request("GET", url, headers=headers)

    templates = response.json()
    return templates


def metrc_api_archive_template(template_id):
    url = (
        METRC_API_BASE_URL
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
                "operationName": "AllDriversVehicles",
                "variables": {},
                "query": "query AllDriversVehicles {\n  viewer {\n    allVehicles {\n      ...vehicleFragment\n      __typename\n    }\n    allDrivers {\n      ...driverFragment\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment vehicleFragment on Vehicle {\n  id\n  name\n  make\n  model\n  licensePlate\n  year\n  __typename\n}\n\nfragment driverFragment on Driver {\n  id\n  firstName\n  lastName\n  driversLicense\n  email\n  phone\n  isArchived\n  onfleetWorkerId\n  __typename\n}\n",
            }
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
    return response.json()


@retry(wait=wait_fixed(5))
def upload_manifest_id(transfer_id, manifest_id):
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
    return response.json()


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

    if "errors" in json_res:
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
        "shipments": SHIPMENTS,
        "total_num_pages": nbr_of_pages,
        "total_num_items": total_nbr_of_resulting_orders,
    }
