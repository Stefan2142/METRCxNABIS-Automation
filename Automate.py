import datetime as dt
from bs4 import BeautifulSoup
import operator
import time
import re
import json
import os
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import selenium.common.exceptions
from selenium.webdriver.support.ui import Select
from api_calls import (
    get_tracker_shipments,
    get_order_data,
    get_nabis_drivers,
    get_nabis_vehicles,
    find_template,
    create_manifest,
    get_metrc_order_and_all_metrc_resources,
    metrc_api_get_template_deliveries,
    metrc_api_get_template_packages,
    metrc_api_find_template,
    metrc_api_archive_template,
    view_metrc_transfer,
    upload_order_note,
    upload_manifest_id,
    upload_manifest_pdf,
)

from routines import (
    get_driver,
    get_spreadsheet_routes,
    finish_template_get_manifest,
    update_log_sheet,
    define_default_logger,
    define_email_logger,
    empty_prices_checker,
    get_cookie_and_token,
    get_traceback,
    duplicate_check,
    send_slack_msg,
    memory_dump,
    thread_fnc,
    metrc_get_facilities,
    get_cwd_files,
    metrc_driver_login,
)
from creds import credentials
from config import paths, WAREHOUSE, nabis_warehouse_licenses
import gspread
import ctypes

counters = {"done": 0, "duplicates": 0, "template_missing": 0, "not_done": 0}

recipient_data = ""
routes = []
logger = define_default_logger()
email_logger = define_email_logger()


def create_metrc_manifest(nabis_order, nabis_order_data, template, driver):
    global recipient_data

    error_log = {}  # These here wont register template/download pdf/update pdf etc

    error_log.update({"Order": nabis_order["orderNumber"]})
    error_log.update({"Shipment": nabis_order["shipmentNumber"]})
    error_log.update({"Warehouse": WAREHOUSE["name"]})

    error_log.update(
        {
            "Date": dt.datetime.strftime(
                dt.datetime.now(dt.datetime.now().astimezone().tzinfo),
                "%Y-%m-%d",
            )
        }
    )
    error_log.update(
        {
            "Timestamp": dt.datetime.strftime(
                dt.datetime.now(dt.datetime.now().astimezone().tzinfo),
                "%Y-%m-%dT%H:%M%z",
            )
        }
    )

    # Get Metrc creds from current webdriver session
    metrc_auth = get_cookie_and_token(driver, WAREHOUSE, credentials)

    template_deliveries = metrc_api_get_template_deliveries(template["Id"])
    template_packages = metrc_api_get_template_packages(template_deliveries[0]["Id"])

    nabis_pkg_data = get_metrc_order_and_all_metrc_resources(nabis_order["orderId"])

    # -----------------------------------------------------------
    #                     Finding recipient id
    # -----------------------------------------------------------

    # use this license to find RecipientId
    destination_license = template_deliveries[0]["RecipientFacilityLicenseNumber"]
    metrc_recipient_id = ""
    if any(
        [
            recipient_data[key]
            for key in recipient_data.keys()
            if recipient_data[key]["LicenseNumber"] == destination_license
        ]
    ):
        metrc_recipient_id = [
            recipient_data[key]
            for key in recipient_data.keys()
            if recipient_data[key]["LicenseNumber"] == destination_license
        ][0]["Id"]
    else:
        logger.error("Couldnt find recipient ID for destination_license")
        error_log.update({"RecipientId": "NotFound"})
        error_log.update({"ALL_GOOD": False})
        return error_log
    error_log.update({"RecipientId": metrc_recipient_id})

    # -----------------------------------------------------------
    #                 Finding recipient license
    # -----------------------------------------------------------

    metrc_recipient_license = ""
    if any(
        [
            value["Id"]
            for key, value in recipient_data.items()
            if value["LicenseNumber"] == destination_license
        ]
    ):
        metrc_recipient_license = [
            value
            for key, value in recipient_data.items()
            if value["LicenseNumber"] == destination_license
        ][0]

    if not metrc_recipient_license:
        error_log.update({"RecipientLicense": "NotFound"})
        error_log.update({"ALL_GOOD": False})
        return error_log
    error_log.update({"RecipientLicense": metrc_recipient_license["LicenseNumber"]})
    logger.debug(f"Found recipient license: {metrc_recipient_license['LicenseNumber']}")
    # -----------------------------------------------------------
    #                      Transfer type
    # -----------------------------------------------------------
    """
    Transfer type id is required by create request to metrc unofficial api
    Transfer shouldnt have prices and Wholesale Manifest should
    """
    metrc_transfer_type = None
    if template_deliveries[0]["ShipmentTypeName"] == "Transfer":
        metrc_transfer_type = {"Name": "Transfer", "Id": "1"}
    if template_deliveries[0]["ShipmentTypeName"] == "Wholesale Manifest":
        metrc_transfer_type = {"Name": "Wholesale Manifest", "Id": "111"}

    # We cant continue if metrc_transfer_type is None
    if not metrc_transfer_type:
        error_log.update({"MetrcTransferType": "NotFound"})
        error_log.update({"ALL_GOOD": False})
        return error_log
    error_log.update({"MetrcTransferType": metrc_transfer_type["Name"]})
    logger.debug(f"Metrc transfer type: {metrc_transfer_type['Name']}")
    # -----------------------------------------------------------
    #                 Adress and route parsing
    # -----------------------------------------------------------

    addresses = (
        template_deliveries[0]["PlannedRoute"]
        .replace(str(nabis_order["orderNumber"]), "")
        .replace("NABIS", "")
        .split("via")[0]
        .replace(" to ", ";")
        .strip()
        .split(";")
    )
    metrc_route = ""
    route_addr_origin = addresses[0].split(", ")[0].strip()
    route_addr_dest = addresses[-1].split(", ")[0].strip()
    route_search_str = f"{route_addr_origin} to {route_addr_dest}"
    if any([route_search_str.lower() in x.lower() for x in routes]):
        metrc_route = [x for x in routes if route_search_str.lower() in x.lower()][0]
        metrc_route = f"NABIS {nabis_order['orderNumber']} " + metrc_route
    else:
        logger.error(
            f"Couldnt find route for: {template_deliveries[0]['PlannedRoute']}"
        )
        error_log.update(
            {
                "CantFindRoute": f"Cant find route in the sheet for planned route (metrc): {template_deliveries[0]['PlannedRoute']}"
            }
        )
        error_log.update({"ALL_GOOD": False})

        return error_log

    if destination_license not in nabis_warehouse_licenses:
        internal_transfer = False
    else:
        internal_transfer = True
    error_log.update({"InternalTransfer": internal_transfer})

    # -----------------------------------------------------------
    #                       Package processing
    # -----------------------------------------------------------

    nabis_line_items = {
        x["metrcPackageTag"]: {
            "quantity": x["quantity"],
            "unit_price": x["pricePerUnit"],
            "total": round((x["pricePerUnit"] * x["quantity"]) - x["discount"], 2),
        }
        for x in nabis_order_data["lineItems"]
    }

    """
    getOnlyMetrcOrder -> tagSequence will give us number of tags allocated
    to only cannabis items (without nc items)
    If there are items with "SKIP"...... [FIND ABOUT THIS]
    """
    if len(
        nabis_pkg_data[0]["data"]["viewer"]["getOnlyMetrcOrder"]["tagSequence"]
    ) != len(template_packages):
        logger.error("Missmatch of number of packages")
        error_log.update({"IncorrectPkgNbr": True})
        error_log.update({"ALL_GOOD": False})
        logger.debug(f"Template pkgs: {template_packages}")
        logger.debug(f"Nabis pkgs: {nabis_pkg_data}")
        return error_log

    # If True - all tags are present in both data sets
    comparison_check = all(
        item in list([x["PackageLabel"] for x in template_packages])
        for item in nabis_pkg_data[0]["data"]["viewer"]["getOnlyMetrcOrder"][
            "tagSequence"
        ]
    )
    if not comparison_check:
        error_log.update({"ComparisonCheck": comparison_check})
        error_log.update({"ALL_GOOD": False})
        logger.error("Missmatch of number of packages")
        logger.debug(f"Template pkgs: {template_packages}")
        logger.debug(f"Nabis pkgs: {nabis_pkg_data}")
        return error_log
    error_log.update({"ComparisonCheck": comparison_check})

    """
    At this point we know that the number of items 
    is the same in template and in the nabis order, and that the tag values 
    are equal to each other across template x nabis order;
    so just assign price from nabis directly instead of relying on template values
    """
    metrc_packages = []
    for template_pkg in template_packages:
        # If type is Wholesale Manifest, we need the price too
        if metrc_transfer_type["Name"] == "Wholesale Manifest":
            wholesale_price = nabis_line_items[template_pkg["PackageLabel"]]["total"]
        else:
            wholesale_price = ""

        metrc_packages.append(
            {
                "Id": template_pkg["PackageId"],
                "WholesalePrice": wholesale_price,
                "GrossWeight": "",
                "GrossUnitOfWeightId": "",
            }
        )
    error_log.update({"PkgNbr": len(metrc_packages)})
    # -----------------------------------------------------------
    #                       Transport details
    # -----------------------------------------------------------
    """
    When driver/vehicle info is missing from Nabis side, 
    nabis_order_data['driver'/'vehicle'] will be None.
    In that case assign flags to be further used with order notes
    """
    transport_detail_flags = {"driver": "", "vehicle": ""}
    transport_details = {
        "driver": {"driversLicense": "temp", "name": "temp"},
        "vehicle": {"make": "temp", "model": "temp", "licensePlate": "temp"},
    }
    if nabis_order_data["driver"]:
        nabis_order_data["driver"][
            "name"
        ] = f"{nabis_order_data['driver']['firstName']} {nabis_order_data['driver']['lastName']}"
    if nabis_order_data["vehicle"]:
        nabis_order_data["vehicle"][
            "model"
        ] = f"{nabis_order_data['vehicle']['name']} {nabis_order_data['vehicle']['model']}"

    for key in transport_detail_flags.keys():
        if not nabis_order_data[key]:
            transport_detail_flags[key] = "FLAG"
        else:
            for detail in transport_details[key].keys():
                transport_details[key][detail] = nabis_order_data[key][detail]

    metrc_manifest_payload = json.dumps(
        [
            {
                "ShipmentLicenseType": template["ShipmentLicenseType"],
                "Destinations": [
                    {
                        "ShipmentLicenseType": template["ShipmentLicenseType"],
                        "RecipientId": metrc_recipient_id,
                        "PlannedRoute": metrc_route,
                        "TransferTypeId": metrc_transfer_type["Id"],
                        "EstimatedDepartureDateTime": template_deliveries[0][
                            "EstimatedDepartureDateTime"
                        ].split(".")[0],
                        "EstimatedArrivalDateTime": template_deliveries[0][
                            "EstimatedArrivalDateTime"
                        ].split(".")[0],
                        "GrossWeight": "",
                        "GrossUnitOfWeightId": "",
                        "Transporters": [
                            {
                                "TransporterId": "142201",
                                "PhoneNumberForQuestions": WAREHOUSE[
                                    "PhoneNumberForQuestions"
                                ],
                                "EstimatedArrivalDateTime": template_deliveries[0][
                                    "EstimatedArrivalDateTime"
                                ].split(".")[0],
                                "EstimatedDepartureDateTime": template_deliveries[0][
                                    "EstimatedDepartureDateTime"
                                ].split(".")[0],
                                "TransporterDetails": [
                                    {
                                        "DriverName": transport_details["driver"][
                                            "name"
                                        ],
                                        "DriverOccupationalLicenseNumber": transport_details[
                                            "driver"
                                        ][
                                            "driversLicense"
                                        ],
                                        "DriverLicenseNumber": transport_details[
                                            "driver"
                                        ]["driversLicense"],
                                        "VehicleMake": transport_details["vehicle"][
                                            "make"
                                        ],
                                        "VehicleModel": transport_details["vehicle"][
                                            "model"
                                        ],
                                        "VehicleLicensePlateNumber": transport_details[
                                            "vehicle"
                                        ]["licensePlate"],
                                    }
                                ],
                            }
                        ],
                        "Packages": metrc_packages,
                    }
                ],
            }
        ]
    )
    logger.debug(f"Manifest payload: {metrc_manifest_payload}")
    logger.debug("Creating manifest...")
    manifest_creation_res = create_manifest(
        metrc_auth["token"],
        metrc_auth["cookie"],
        WAREHOUSE["license"],
        metrc_manifest_payload,
    )
    logger.debug(f"Manifest creation complete; Result: {manifest_creation_res}")
    try:
        # {'Ids': [], 'Messages': []}
        # Not created
        if manifest_creation_res["Ids"] == []:
            # Empty
            logger.error(
                "Submitted template data was probably incorrect, template wasnt registered"
            )
            error_log.update(
                {"ManifestCreateError": "Template not registered; Data incorrect"}
            )
            logger.error(
                f"Manifest payload: {metrc_manifest_payload}; metrc token: {metrc_auth['token']}; metrc cookie: {metrc_auth['cookie']}; warehouse license: {WAREHOUSE['license']}; manifest creation res: {manifest_creation_res}"
            )
            error_log.update({"ALL_GOOD": "FALSE"})
            return error_log
    except KeyError:
        pass
    try:
        # {'Message': 'An error has occurred.'}
        # Not created
        if manifest_creation_res["Message"]:
            logger.error(f"Manifest creation error: {manifest_creation_res['Message']}")
            error_log.update({"ManifestCreateError": manifest_creation_res["Message"]})
            logger.error(
                f"Manifest payload: {metrc_manifest_payload}; metrc token: {metrc_auth['token']}; metrc cookie: {metrc_auth['cookie']}; warehouse license: {WAREHOUSE['license']}; manifest creation res: {manifest_creation_res}"
            )
            error_log.update({"ALL_GOOD": "FALSE"})
            return error_log
    except KeyError:
        pass

    # -----------------------------------------------------------
    #                     Find the manifest pdf
    # -----------------------------------------------------------

    # {'Ids': [3460305], 'Messages': []}
    metrc_manifest_id = manifest_creation_res["Ids"][0]
    error_log.update({"ManifestId": metrc_manifest_id})

    logger.info("Downloading manifest file...")
    current_files = len(get_cwd_files())
    driver.execute_script(
        f"""
            var link = document.createElement("a");
                link.href = 'https://ca.metrc.com/reports/transfers/{WAREHOUSE['license']}/manifest?id={metrc_manifest_id}';
                link.download = "name.pdf";
                link.click();
            """
    )

    while current_files == len(get_cwd_files()):
        pass
    time.sleep(0.7)
    list_of_pdf = get_cwd_files()
    list_of_pdf = filter(lambda pdf: ".pdf" in pdf, list_of_pdf)
    list_of_pdf = list(list_of_pdf)

    # logger.info(f"[{nabis_order['id']}] File downloaded {list_of_pdf[0]}")

    # o = get_order_data(nabis_order["orderNumber"])
    transfer = view_metrc_transfer(nabis_order["orderId"])
    transfer_id = ""
    try:
        transfer_id = [
            x["id"]
            for x in transfer["data"]["getMetrcTransfers"]
            if template["Name"] == x["metrcTransferTemplateName"]
        ][0]
    except IndexError:
        logger.error(
            f"Couldnt get Nabis transfer ID for the order {nabis_order['orderNumber']}, manifest: {metrc_manifest_id}"
        )
        error_log.update(
            {
                "RequiresManualFinish": f"Upload the manifest ({metrc_manifest_id}) pdf to order: {nabis_order['orderNumber']}, shipment: {nabis_order['shipmentNumber']}"
            }
        )
        error_log.update({"ALL_GOOD": "FALSE"})
        return error_log
    if transfer_id == "":
        logger.error(
            f"Couldnt get Nabis transfer ID for the order {nabis_order['orderNumber']}, manifest: {metrc_manifest_id}"
        )
        error_log.update(
            {
                "RequiresManualFinish": f"Upload the manifest ({metrc_manifest_id}) pdf to order: {nabis_order['orderNumber']}, shipment: {nabis_order['shipmentNumber']}"
            }
        )
        error_log.update({"ALL_GOOD": "FALSE"})
        return error_log

    logger.info(f"[{nabis_order['id']}] list_of_pdfs: {list_of_pdf}")
    logger.info(f"[{nabis_order['id']}] File to be uploaded {list_of_pdf[0]}")

    order_notes = ""
    for k, v in transport_detail_flags.items():
        if v == "FLAG":
            order_notes += f"TEMP {k};"
    if order_notes != "":
        logger.info(f"[{nabis_order['id']}] Uploading order notes: {order_notes}")
        order_note_response = upload_order_note(transfer_id, order_notes)
        logger.debug(f"Order note response: {order_note_response}")
        error_log.update({"OrderNotes": order_notes})
    else:
        logger.info("No order notes")

    pdf_response = upload_manifest_pdf(transfer_id, paths["pdfs"] + list_of_pdf[0])
    id_response = upload_manifest_id(transfer_id, metrc_manifest_id)
    logger.debug(f"PDF response: {pdf_response}; ID response: {id_response}")

    if (pdf_response == "errors") or (pdf_response == False):
        logger.error(
            f'Error while uploading manifest pdf {transfer_id}, order: {nabis_order["orderNumber"]}'
        )
        error_log.update(
            {
                "RequiresManualFinish": f"Upload the manifest: ({metrc_manifest_id}) pdf to order: {nabis_order['orderNumber']}, shipment: {nabis_order['shipmentNumber']}"
            }
        )
        error_log.update({"ALL_GOOD": "FALSE"})
    if ("errors" == id_response) or (id_response == False):
        logger.error(
            f'Error while uploading manifest id number {transfer_id}, order {nabis_order["orderNumber"]}'
        )
        error_log.update(
            {
                "RequiresManualFinish": f"Upload the manifest ({metrc_manifest_id}) id to order: {nabis_order['orderNumber']}, shipment: {nabis_order['shipmentNumber']}"
            }
        )
        error_log.update({"ALL_GOOD": "FALSE"})

    # Delete the template
    metrc_archive_response = metrc_api_archive_template(template["Id"])

    logger.debug(f"Metrc delete template action: {metrc_archive_response}")
    counters["done"] += 1

    error_log.update({"ALL_GOOD": "TRUE"})
    return error_log
    # return {
    #     "manifest_id": metrc_manifest_id,
    #     "pdf_response": pdf_response,
    #     "id_response": id_response,
    #     "order_note": order_notes,
    # }


def find_metrc_order(
    wait, driver, nabis_shipment, nabis_order_id, nabis_order_line_items, nabis_order
):
    global logger
    """Click on three dots for filtering where we have 6 elements with same class name;
    Those represent 6 columns that allow filtering;
    We always need the first one 'Template' column;
    So by using 'find_elements' instead of find_element,
    we are clicking on the first(0th) element in that array


    Args:
        wait (WebDriverWait): used for implementing browser waits
        driver (webdriver): web browser instance
        nabis_order_id (int): order id from nabis whose template we are looking for
        nabis_order_line_items (lst with dicts): line items for nabis order
        nabis_order (dict): whole nabis order object

    Returns:
        _type_: _description_
    """

    try:
        driver.find_element(by=By.CLASS_NAME, value="k-header-column-menu").click()
    except selenium.common.exceptions.ElementClickInterceptedException:
        driver.get(
            f"https://ca.metrc.com/industry/{WAREHOUSE['license']}/transfers/licensed/templates"
        )
        time.sleep(0.3)
        wait.until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "k-loading-text"))
        )
        driver.find_element(by=By.CLASS_NAME, value="k-header-column-menu").click()

    time.sleep(0.5)

    # Click on 'Filter' sub-menu
    try:
        driver.find_element(by=By.CLASS_NAME, value="k-icon.k-i-filter").click()
    except:
        driver.find_element(by=By.CLASS_NAME, value="k-header-column-menu").click()
        driver.find_element(by=By.CLASS_NAME, value="k-icon.k-i-filter").click()
        time.sleep(0.5)

    # Filter input box, clear and input order number
    try:
        wait.until(
            EC.visibility_of_element_located(
                (By.XPATH, '//*[@title="Filter Criteria"]')
            )
        )
    except:
        driver.find_element(by=By.CLASS_NAME, value="k-icon.k-i-filter").click()
        time.sleep(1)

    driver.find_element(by=By.XPATH, value='//*[@title="Filter Criteria"]').clear()
    driver.find_element(by=By.XPATH, value='//*[@title="Filter Criteria"]').send_keys(
        str(nabis_order_id)
    )

    # Click on 'Filter' button
    driver.find_element(by=By.CLASS_NAME, value="k-button.k-primary").click()
    wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "k-loading-text")))
    time.sleep(0.5)

    # If search result is empty
    # If <list> results is empty, there are no results for a given order
    results = driver.find_elements(
        by=By.CLASS_NAME, value="k-grid-norecords.grid-no-data"
    )
    if len(results) > 0:
        logger.error(
            f"Results not found for order {nabis_order_id}, {len(results)} {results}"
        )
        return False
    else:
        logger.info(f"Metrc search result for order: {nabis_order_id} found!")

        bool = True
        while bool:
            try:
                time.sleep(0.7)
                driver.find_element(
                    by=By.CLASS_NAME,
                    value="k-button.k-button-icontext.grid-row-button.k-grid-Use",
                ).click()
                bool = False
            except:
                pass
    logger.info(
        "Clicked on 'Use template' (Exited previous while loop!). Waiting for template"
    )

    ### MISSING LOGIC FOR PICKING A CORRECT ROW ###

    # Waiting for the Transfer pop-up to display
    bool = True
    while bool:
        try:
            time.sleep(0.5)

            driver.find_element(
                by=By.NAME,
                value="model[0][Destinations][0][Transporters][0][TransporterDetails][0][VehicleMake]",
            )
            bool = False
            continue
        except:
            pass
        try:
            driver.find_element(By.CLASS_NAME, value="k-loading-image")

        except:
            if bool:
                try:
                    driver.find_element(
                        by=By.CLASS_NAME,
                        value="k-button.k-button-icontext.grid-row-button.k-grid-Use",
                    ).click()
                except:
                    pass
            else:
                bool = False

    logger.info("Template loaded. Begin matching...")
    log_dict = proc_template(
        driver, nabis_order_id, nabis_order_line_items, nabis_order, nabis_shipment
    )
    return log_dict


def proc_template(
    driver, nabis_order_id, nabis_order_line_items, nabis_order, nabis_shipment
):
    from config import matching_attrs

    global logger
    global counters
    soup = BeautifulSoup(driver.page_source, "html.parser")
    script_element = soup.find(text=re.compile("repeaterData"))
    raw_json = script_element[
        script_element.find("JSON.parse") : script_element.rfind("x7d'),")
    ]

    json_str = bytes(raw_json.encode("utf8"))[:-1:].decode("unicode-escape")
    json_str = json_str + "}"
    json_dict = json.loads(json_str[12:])
    # Free memory
    del script_element
    del soup
    del raw_json
    del json_str

    log_dict = {}
    transport_details_log = {}

    metrc_packages = [
        x for x in json_dict["Packages"] if str(nabis_order_id) in x["Note"]
    ]

    # Add wholesale price for tags on Metrc side
    for tag in metrc_packages:
        if any(
            [
                tag["Id"] == x["Id"]
                for x in json_dict["Details"][0]["Destinations"][0]["Packages"]
            ]
        ):
            tag.update(
                {
                    "WholesalePrice": [
                        x["WholesalePrice"]
                        for x in json_dict["Details"][0]["Destinations"][0]["Packages"]
                        if tag["Id"] == x["Id"]
                    ][0]
                }
            )

    nabis_packages = {
        x["metrcPackageTag"]: {
            "quantity": x["quantity"],
            "unit_price": x["pricePerUnit"],
            "total": round((x["pricePerUnit"] * x["quantity"]) - x["discount"], 2),
        }
        for x in nabis_order_line_items
    }

    try:
        metrc_transfer_type = Select(
            driver.find_element(
                By.XPATH, value='//*[@ng-model="destination.TransferTypeId"]'
            )
        ).first_selected_option.text

        # Select(
        #     driver.find_element(
        #         By.XPATH, value='//*[@ng-model="destination.TransferTypeId"]'
        #     )
        # ).select_by_visible_text('Transfer')
        # ili 'Wholesale Manifest'

    except:
        metrc_transfer_type = ""

    if metrc_transfer_type == "":
        log_dict.update({"UnreadableTransferType": "TRUE"})  # ✅

    def update_log(dct, key, error_type, error_msg):
        dct.update(
            {
                matching_attrs[key][error_type]: matching_attrs[key][error_msg].format(
                    matching_attrs[key]["metrc"]["data"],
                    matching_attrs[key]["nabis"]["data"],
                )
            }
        )

    def temp_none_check(key):
        """Helper function to test if nabis data isnt equal to '' and
        metrc not to 'temp' return True.
        In this scenario we check if driver and vehicle info is empty on both sides;
        If it is, skip these checks and label them as correct.
        NEW UPDATE 2022-03-29: If nabis data is equal to '' and metrc to 'temp':
            label it as incorrect (return False).
            If metrc data is 'temp', fill in from the nabis data to webpage and return True.
        Args:
            metrc_str (str): metrc data
            nabis_str (str): nabis data
        Returns:
            bool: _description_
        """
        # If both fields are empty return True
        if (str(matching_attrs[key]["metrc"]["data"]).lower().strip() == "temp") and (
            str(matching_attrs[key]["nabis"]["data"]).lower().strip() == ""
        ):
            # Ovde update-ovati drugi log koji ce se na kraju dodati na log_dict
            # Jer zelimo da nam ostane gde je temp da znamo
            update_log(
                transport_details_log, key, "error_missing_key", "error_missing_msg"
            )
            return "Empty"
        if (str(matching_attrs[key]["metrc"]["data"]).lower().strip() == "temp") and (
            str(matching_attrs[key]["nabis"]["data"]).lower().strip() != ""
        ):
            # Clear the field
            driver.find_element(
                By.XPATH, value=matching_attrs[key]["metrc_key"]
            ).clear()
            time.sleep(0.3)
            # Send data
            driver.find_element(
                By.XPATH, value=matching_attrs[key]["metrc_key"]
            ).send_keys(matching_attrs[key]["nabis"]["data"])
            time.sleep(0.3)

            matching_attrs[key]["metrc"]["data"] = driver.find_element(
                by=By.XPATH,
                value=matching_attrs[key]["metrc_key"],
            ).get_attribute("value")

            return "Assigned"
        if (
            str(matching_attrs[key]["nabis"]["data"]).lower().strip()
            == str(matching_attrs[key]["metrc"]["data"]).lower().strip()
        ) or (
            str(matching_attrs[key]["nabis"]["data"]).lower().strip()
            in str(matching_attrs[key]["metrc"]["data"]).lower().strip()
        ):
            return "Match"
        else:
            # Ovde pravi log update-ovati
            update_log(log_dict, key, "error_incorrect_key", "error_incorrect_msg")
            return "Missmatch"

    # Mozda dodati jos jednu kolonu za driver/vehicle tipa:
    # TransportDetail: Empty/Assigned/Match/Missmatch

    matching_attrs["license"]["metrc"]["data"] = driver.find_element(
        by=By.XPATH, value=matching_attrs["license"]["metrc_key"]
    ).get_attribute("value")
    matching_attrs["license"]["nabis"]["data"] = nabis_order["siteLicenseNum"]

    if (
        matching_attrs["license"]["metrc"]["data"].strip().lower()
        != matching_attrs["license"]["nabis"]["data"].strip().lower()
    ):
        # If its internal transfer, they dont need to match
        if (
            matching_attrs["license"]["metrc"]["data"].strip()
            not in nabis_warehouse_licenses
        ):
            update_log(
                log_dict, "license", "error_incorrect_key", "error_incorrect_msg"
            )

    # Check if its internal transfer
    if (
        matching_attrs["license"]["metrc"]["data"].strip()
        not in nabis_warehouse_licenses
    ):
        internal_transfer = False
    else:
        internal_transfer = True

    matching_attrs["route"]["metrc"]["data"] = driver.find_element(
        by=By.NAME, value=matching_attrs["route"]["metrc_key"]
    ).get_attribute("value")

    # DATE MATCHING
    matching_attrs["est_departure_date"]["metrc"]["data"] = dt.datetime.strptime(
        json_dict["Details"][0]["Destinations"][0]["EstimatedDepartureDateTime"],
        "%Y-%m-%dT%H:%M:%S.%f",
    )

    matching_attrs["est_arrival_date"]["metrc"]["data"] = dt.datetime.strptime(
        json_dict["Details"][0]["Destinations"][0]["EstimatedArrivalDateTime"],
        "%Y-%m-%dT%H:%M:%S.%f",
    )

    if (
        matching_attrs["est_departure_date"]["metrc"]["data"].date()
        != matching_attrs["est_arrival_date"]["metrc"]["data"].date()
    ):
        log_dict.update(
            {
                "IncorrectDates": "Metrc dep. and arr. dates are different; Depart: {}, Arrival: {}".format(
                    matching_attrs["est_departure_date"]["metrc"]["data"].date(),
                    matching_attrs["est_arrival_date"]["metrc"]["data"].date(),
                )
            }
        )
    # Get the time from the ajax json response
    # For both, departure and arrival

    # Departure time
    metrc_est_dept_time = json_dict["Details"][0]["Destinations"][0][
        "EstimatedDepartureDateTime"
    ]
    metrc_est_dept_time = dt.datetime.strptime(
        metrc_est_dept_time.split("T")[-1], "%H:%M:%S.%f"
    )

    # Arrival time
    metrc_est_arr_time = json_dict["Details"][0]["Destinations"][0][
        "EstimatedArrivalDateTime"
    ]
    metrc_est_arr_time = dt.datetime.strptime(
        metrc_est_arr_time.split("T")[-1], "%H:%M:%S.%f"
    )

    # Free memory
    del json_dict
    dt.datetime.now().date()
    matching_attrs["est_departure_date"]["metrc"]["data"].date() - dt.timedelta(days=1)

    transport_details = {
        "driver": {
            "driver": ["firstName", "lastName"],
            "driver_id": ["driversLicense"],
        },
        "vehicle": {
            "vehicle_make": ["make"],
            "vehicle_model": ["name"],
            "vehicle_plate": ["licensePlate"],
        },
    }

    transport_detail_flags = {"driver": "", "vehicle": ""}

    for transport_detail in transport_details.keys():
        if nabis_order[transport_detail] == None:
            transport_detail_flags[
                [
                    x
                    for x in list(transport_detail_flags.keys())
                    if x == transport_detail
                ][0]
            ] = "FLAG"
            continue
        for transport_detail_key in transport_details[transport_detail].keys():
            matching_attrs[transport_detail_key]["metrc"]["data"] = driver.find_element(
                by=By.XPATH,
                value=matching_attrs[transport_detail_key]["metrc_key"],
            ).get_attribute("value")
            s = ""

            for transport_attr in transport_details[transport_detail][
                transport_detail_key
            ]:
                s += f"{nabis_order[transport_detail][transport_attr].strip()} "

            matching_attrs[transport_detail_key]["nabis"]["data"] = s.strip()

            # If values are 'temp' and ''
            # If values are not ''
            temp_check_result = temp_none_check(transport_detail_key)
            if temp_check_result == "Empty":
                transport_detail_flags[
                    [
                        x
                        for x in list(transport_detail_flags.keys())
                        if x == transport_detail
                    ][0]
                ] = "FLAG"
            logger.info(
                f"TransportDetailKey '{transport_detail_key}' matching result: {temp_check_result}"
            )

    # Address & route parsing
    addresses = (
        matching_attrs["route"]["metrc"]["data"]
        .replace(str(nabis_order_id), "")
        .replace("NABIS", "")
        .split("via")[0]
        .replace(" to ", ";")
        .strip()
        .split(";")
    )

    route_addr_origin = addresses[0].split(", ")[0].strip()
    route_addr_dest = addresses[-1].split(", ")[0].strip()
    route_search_str = f"{route_addr_origin} to {route_addr_dest}"
    if any([route_search_str.lower() in x.lower() for x in routes]):
        matching_attrs["route"]["metrc"]["data"] = [
            x for x in routes if route_search_str.lower() in x.lower()
        ][0]
        matching_attrs["route"]["metrc"]["data"] = (
            f"NABIS {nabis_order_id} " + matching_attrs["route"]["metrc"]["data"]
        )

    else:

        log_dict.update(
            {
                "CantFindRoute": f"Cant find route in the sheet for planned route (metrc): {matching_attrs['route']['metrc']['data']}"
            }
        )
    # If there is missing child package tag msg in the extension,
    # this is the same.

    if any([None == x for x in list(nabis_packages.keys())]):
        pkg_data = get_metrc_order_and_all_metrc_resources(nabis_order["id"])
        if len(
            pkg_data[0]["data"]["viewer"]["getOnlyMetrcOrder"]["tagSequence"]
        ) == len(pkg_data[0]["data"]["viewer"]["getOnlyMetrcOrder"]["lineItems"]):
            log_dict = {
                "MissingChildPackageTag": "Error: One line item doesnt have metrc tag"
            }
            logger.debug(
                "MissingChildPackageTag: Error - One line item doesnt have metrc tag"
            )
        else:
            missing_child_package = {
                "MissingChildPackageTag": "Warning: One line item doesnt have metrc tag"
            }
            logger.debug(
                "MissingChildPackageTag: Warning - One line item doesnt have metrc tag"
            )
    else:
        missing_child_package = {"MissingChildPackageTag": ""}

        # log_dict.update(
        #     {"MissingChildPackageTag": "One line item doesnt have metrc tag"}
        # )

    metrc_only_tags = {}
    for x in metrc_packages:
        d = {}
        if "WholesalePrice" in x:
            d["WholesalePrice"] = x["WholesalePrice"]
        else:
            d["WholesalePrice"] = 0

        if "Quantity" in x:
            d["quantity"] = x["Quantity"]
        else:
            d["quantity"] = 0

        metrc_only_tags[x["Label"]] = d

    # del nabis_packages['SKIP]
    if len(nabis_packages) != len(metrc_only_tags):
        # SKIP tags are nc (non cannabis items)
        if "SKIP" not in nabis_packages.keys():
            if None not in nabis_packages.keys():
                log_dict.update(
                    {
                        "IncorrectPkgNbr": f"Mismatch of number of packages between metrc and nabis; Metrc: {len(metrc_only_tags)}, Nabis: {len(nabis_packages)}"
                    }
                )
                logger.warning("Number of packages not the same!!!")
    else:
        logger.info("Number of packages is the same!!!")

    def metrc_prices_helper():
        """This function will return True if
        wholesale price of all metrc packages is none or 0.
        If there is even one package with price it will return False.

        Returns:
            bool: flag
        """
        nonlocal metrc_only_tags

        for x in list(metrc_only_tags.keys()):
            if metrc_only_tags[x]["WholesalePrice"] != None:
                return False
        return True

    all_metrc_prices_none = metrc_prices_helper()

    # RULE: If its internal transfer and all prices are none, change
    # dates
    if (all_metrc_prices_none == True) and (internal_transfer == True):

        # EST Departure date
        driver.find_element(
            By.XPATH, value='//*[@ng-model="destination.EstimatedDepartureDateTime"]'
        ).clear()
        driver.find_element(
            By.XPATH, value='//*[@ng-model="destination.EstimatedDepartureDateTime"]'
        ).send_keys(
            dt.datetime.strftime(dt.datetime.now() + dt.timedelta(days=1), "%m/%d/%Y")
        )

        # When pasting dates, a calendar pop-up will appear, click
        # on other element so the calendar pop-up will disappear
        driver.find_element(
            by=By.NAME, value="model[0][Destinations][0][PlannedRoute]"
        ).click()
        time.sleep(0.3)

        # When pasting dates, time resets, bring it back
        metrc_est_dept_time_el = driver.find_element(
            By.XPATH, value='//div[@ng-model="destination.EstimatedDepartureDateTime"]'
        )
        hours = metrc_est_dept_time.hour
        if metrc_est_dept_time.hour > 12:
            # Switch AM/PM
            if (
                metrc_est_dept_time_el.find_element(
                    by=By.CLASS_NAME, value="btn.text-center.ng-binding"
                ).text
                != "PM"
            ):
                metrc_est_dept_time_el.find_element(
                    by=By.CLASS_NAME, value="btn.text-center.ng-binding"
                ).click()
                hours = hours - 12
        metrc_est_dept_time_el.find_element(
            by=By.XPATH, value='//input[@ng-model="hours"]'
        ).clear()
        metrc_est_dept_time_el.find_element(
            by=By.XPATH, value='//input[@ng-model="hours"]'
        ).send_keys(hours)
        metrc_est_dept_time_el.find_element(
            by=By.XPATH, value='//input[@ng-model="minutes"]'
        ).clear()
        metrc_est_dept_time_el.find_element(
            by=By.XPATH, value='//input[@ng-model="minutes"]'
        ).send_keys(metrc_est_dept_time.minute)

        # EST Arrival date
        driver.find_element(
            By.XPATH, value='//*[@ng-model="destination.EstimatedArrivalDateTime"]'
        ).clear()
        driver.find_element(
            By.XPATH, value='//*[@ng-model="destination.EstimatedArrivalDateTime"]'
        ).send_keys(
            dt.datetime.strftime(dt.datetime.now() + dt.timedelta(days=1), "%m/%d/%Y")
        )
        # When pasting dates, a calendar pop-up will appear, click
        # on other element so the calendar pop-up will disappear
        driver.find_element(
            by=By.NAME, value="model[0][Destinations][0][PlannedRoute]"
        ).click()
        time.sleep(0.3)
        # When pasting dates, time resets, bring it back
        metrc_est_arr_time_el = driver.find_element(
            By.XPATH, value='//div[@ng-model="destination.EstimatedArrivalDateTime"]'
        )
        hours = metrc_est_arr_time.hour
        if hours > 12:
            # Switch AM/PM
            if (
                metrc_est_arr_time_el.find_element(
                    by=By.CLASS_NAME, value="btn.text-center.ng-binding"
                ).text
                != "PM"
            ):
                metrc_est_arr_time_el.find_element(
                    by=By.CLASS_NAME, value="btn.text-center.ng-binding"
                ).click()
                hours = hours - 12
        metrc_est_arr_time_el.find_element(
            by=By.XPATH, value='.//input[@ng-model="hours"]'
        ).clear()
        metrc_est_arr_time_el.find_element(
            by=By.XPATH, value='.//input[@ng-model="hours"]'
        ).send_keys(hours)
        metrc_est_arr_time_el.find_element(
            by=By.XPATH, value='.//input[@ng-model="minutes"]'
        ).clear()
        metrc_est_arr_time_el.find_element(
            by=By.XPATH, value='.//input[@ng-model="minutes"]'
        ).send_keys(metrc_est_arr_time.minute)

    for i in nabis_packages.keys():
        if i == "SKIP":
            if i != None:
                if not metrc_only_tags.get(i):
                    # tag is missing
                    if "MissingPackageTag" not in log_dict:
                        log_dict.update(
                            {
                                "MissingPackageTag": [
                                    f"Tag exists in nabis but not in metrc template. NabisTagId: '{i}'"
                                ]
                            }
                        )
                    else:
                        log_dict["MissingPackageTag"].extend(
                            {
                                "MissingPackageTag": [
                                    f"Tag exists in nabis but not in metrc template. NabisTagId: '{i}'"
                                ]
                            }
                        )

                else:
                    if nabis_packages[i]["quantity"] != metrc_only_tags[i]["quantity"]:
                        if "WrongQuantity" not in log_dict:
                            log_dict.update(
                                {
                                    "WrongQuantity": [
                                        f"Incorrect quantity; Metrc: {metrc_only_tags[i]['quantity']}, Nabis: {nabis_packages[i]['quantity']}"
                                    ]
                                }
                            )
                        else:
                            log_dict["WrongQuantity"].extend(
                                [
                                    f"Incorrect quantity; Metrc: {metrc_only_tags[i]['quantity']}, Nabis: {nabis_packages[i]['quantity']}"
                                ]
                            )

                    else:
                        logger.info(f"Quantities good for {i};")

                    ### AKO JE TRANSFER A NE WHOLESALE MANIFEST

                    if (
                        nabis_packages[i]["total"]
                        != metrc_only_tags[i]["WholesalePrice"]
                    ):

                        if (metrc_transfer_type != "Transfer") and (
                            all_metrc_prices_none == False
                        ):
                            if "WrongPrice" not in log_dict:
                                log_dict.update(
                                    {
                                        "WrongPrice": [
                                            f"Incorrect price ({i}); Metrc: {metrc_only_tags[i]['WholesalePrice']}, Nabis: {nabis_packages[i]['total']}"
                                        ]
                                    }
                                )
                            else:
                                log_dict["WrongPrice"].extend(
                                    [
                                        f"Incorrect price ({i}); Metrc: {metrc_only_tags[i]['WholesalePrice']}, Nabis: {nabis_packages[i]['total']}"
                                    ]
                                )

                        else:
                            logger.info(
                                "Price missing on metrc side but template type is Transfer"
                            )
                    else:
                        logger.info(f"Prices good for {i};")
        else:
            pass

    # PROCEDURES FOR ROUTE EDITING
    driver.find_element(
        by=By.NAME, value="model[0][Destinations][0][PlannedRoute]"
    ).click()

    driver.find_element(
        by=By.NAME, value="model[0][Destinations][0][PlannedRoute]"
    ).clear()

    driver.find_element(
        by=By.NAME, value="model[0][Destinations][0][PlannedRoute]"
    ).send_keys(matching_attrs["route"]["metrc"]["data"])

    time.sleep(1)

    shipment = list(
        filter(
            lambda word: word[0] == "#",
            nabis_order["shipment_template"].split(),
        )
    )[0]
    logger.debug("Matching attrs:")
    logger.debug(json.dumps(matching_attrs, indent=2, default=str))
    logger.debug("Nabis packages:")
    logger.debug(json.dumps(nabis_packages, indent=2, default=str))
    logger.debug("Metrc packages:")
    logger.debug(json.dumps(metrc_only_tags, indent=2, default=str))

    if log_dict:
        logger.info(f"Log for order: {nabis_order_id}:")
        logger.info(json.dumps(log_dict, indent=2))
        log_dict.update({"InternalTransfer": internal_transfer})
        log_dict.update({"TransferType": metrc_transfer_type})
        log_dict.update({"ALL_GOOD": "FALSE"})
        log_dict.update({"ManifestId": ""})
        # send_slack_msg(f"\t ❌ Order: {nabis_order_id} failed. Check gsheet log.")
        counters["not_done"] += 1

        # finish_template_get_manifest(driver, WAREHOUSE['license'], nabis_order)
    else:
        if (empty_prices_checker(driver) == True) and (
            metrc_transfer_type.strip() == "Wholesale Manifest"
        ):
            logger.info(f"Log for order: {nabis_order_id}:")
            logger.info(json.dumps(log_dict, indent=2, default=str))
            log_dict.update(missing_child_package)
            log_dict.update({"PricesEmpty": "TRUE"})
            log_dict.update({"InternalTransfer": internal_transfer})
            log_dict.update({"TransferType": metrc_transfer_type})
            log_dict.update({"ALL_GOOD": "FALSE"})
            counters["not_done"] += 1
            # send_slack_msg(f"\t ❌ Order: {nabis_order_id} failed. Check gsheet log.")

        else:
            logger.info(
                f"---All checks good: {nabis_order_id} / ({shipment}) uploading pdf and id!---"
            )
            if (empty_prices_checker(driver) == True) and (
                metrc_transfer_type.strip() == "Wholesale Manifest"
            ):
                logger.info(
                    "Template has empty prices and type Wholesale Manifest, changing to Transfer"
                )
                Select(
                    driver.find_element(
                        By.XPATH, value='//*[@ng-model="destination.TransferTypeId"]'
                    )
                ).select_by_visible_text("Transfer")
                logger.info("Type changed!")
                metrc_transfer_type = f"{metrc_transfer_type}_x_Transfer"

            log_dict.update({"TransferType": metrc_transfer_type})
            log_dict.update(missing_child_package)

            finish_status = []
            finish_status = finish_template_get_manifest(
                driver,
                WAREHOUSE["license"],
                nabis_order,
                transport_detail_flags,
                logger,
            )
            if not finish_status:
                log_dict.update(
                    {
                        "ALL_GOOD": f"FALSE - Couldnt find recently created manifest for id {nabis_order_id}"
                    }
                )
                send_slack_msg(
                    f"\t ❌ Order: {nabis_order_id} registered. Couldnt find recently created manifest. Do it manually."
                )
                counters["not_done"] += 1
            else:

                log_dict.update({"OrderNote": finish_status["order_note"]})

                if finish_status["pdf_response"] == False:
                    log_dict.update(
                        {"ALL_GOOD": "FALSE - Template regsitered. PDF not updated"}
                    )
                    counters["not_done"] += 1
                    send_slack_msg(
                        f"\t ❌ Order: {nabis_order_id} registered. Failure at manifest pdf upload. Do it manually. (Manifest nbr: {finish_status['manifest_id']})"
                    )

                elif finish_status["id_response"] == False:
                    log_dict.update(
                        {
                            "ALL_GOOD": "FALSE - Template regsitered. Manifest ID not updated"
                        }
                    )
                    counters["not_done"] += 1
                    send_slack_msg(
                        f"\t ❌ Order: {nabis_order_id} registered. Failure at manifest id upload. Do it manually. (Manifest nbr: {finish_status['manifest_id']})"
                    )
                else:
                    log_dict.update({"ALL_GOOD": "TRUE"})
                    log_dict.update(transport_details_log)
                    counters["done"] += 1

                log_dict.update({"ManifestId": finish_status["manifest_id"]})
            log_dict.update({"InternalTransfer": internal_transfer})

    log_dict.update({"Order": str(nabis_order_id)})
    log_dict.update({"Shipment": str(shipment)})
    log_dict.update({"PkgNbr": len(nabis_packages)})
    log_dict.update({"Warehouse": WAREHOUSE["name"]})
    # log_dict.update({"TransportMatchAction": temp_check_result})
    log_dict.update(
        {
            "Date": dt.datetime.strftime(
                dt.datetime.now(dt.datetime.now().astimezone().tzinfo),
                "%Y-%m-%d",
            )
        }
    )
    log_dict.update(
        {
            "Timestamp": dt.datetime.strftime(
                dt.datetime.now(dt.datetime.now().astimezone().tzinfo),
                "%Y-%m-%dT%H:%M%z",
            )
        }
    )

    try:
        driver.get(
            f"https://ca.metrc.com/industry/{WAREHOUSE['license']}/transfers/licensed/templates"
        )
    except:
        time.sleep(7)
        driver.get(
            f"https://ca.metrc.com/industry/{WAREHOUSE['license']}/transfers/licensed/templates"
        )
    return log_dict


def main():
    global routes
    global logger
    global counters
    import operator

    global recipient_data

    gc = gspread.service_account(filename="./emailsending-325211-e5456e88f282.json")

    import threading

    proc = threading.Thread(target=thread_fnc, args=(gc,), daemon=True)
    proc.start()

    for k, v in paths.items():
        try:
            Path(v).mkdir(parents=True, exist_ok=True)
        except:
            pass

    def kill_thread(thread):
        """
        thread: a threading.Thread object
        """
        thread_id = thread.ident
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            thread_id, ctypes.py_object(SystemExit)
        )
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print("Exception raise failure")

    session_start_time = time.perf_counter()
    try:
        logger.info(
            f"##----------SESSION STARTED with warehouse: {WAREHOUSE['name']}----------##"
        )

        # send_slack_msg(
        #     "#-----▶ {:^40s} ▶-----#".format(
        #         f"SESSION STARTED BY USER: {os.getenv('CLIENTNAME')}, for the warehouse: {WAREHOUSE['name']}"
        #     )
        # )

        logger.info("Getting routes from gsheet...")
        routes = get_spreadsheet_routes(gc)
        logger.info("Initializing Chrome WebDriver...")
        driver = get_driver()
        driver.implicitly_wait(0.5)
        wait = WebDriverWait(driver, 180)

        driver = metrc_driver_login(driver, WAREHOUSE, credentials)
        if not driver:
            raise Exception("Couldnt login")

        recipient_data = metrc_get_facilities(driver)
        if not recipient_data:
            logger.error(
                f"No templates to pick from (WAREHOUSE: {WAREHOUSE}) in order to fetch Facility IDs"
            )
            return False

        # Getting date for nabis shipment query
        # IF today is friday, 'tomorrow' should be monday
        if dt.datetime.today().weekday() == 4:
            if dt.datetime.today().hour >= 6:
                tomorrow = dt.datetime.strftime(
                    dt.datetime.now() + dt.timedelta(days=3), "%m-%d-%Y"
                )
            else:
                tomorrow = dt.datetime.strftime(dt.datetime.now(), "%m-%d-%Y")

        else:
            if dt.datetime.today().hour >= 6:
                tomorrow = dt.datetime.strftime(
                    dt.datetime.now() + dt.timedelta(days=1), "%m-%d-%Y"
                )
            else:
                tomorrow = dt.datetime.strftime(dt.datetime.now(), "%m-%d-%Y")

        logger.info(f"Working with date {tomorrow}")
        logger.info("Getting shipments from Nabis...")
        # Get nabis tracker shipments
        res = get_tracker_shipments(tomorrow)

        if res == False:
            logger.info("Error while getting shipments from Nabis. Exiting...")
            send_slack_msg(f"Error while getting shipments from Nabis. Exiting...")
            exit(1)

        # total number of pages
        total_num_pages = res["total_num_pages"]

        # Total number of resulting orders for given query
        total_num_items = res["total_num_items"]
        if total_num_items == 0:
            logger.info(f"No orders to work on for date {tomorrow}")
            send_slack_msg(f"No orders to work on for date {tomorrow}")
            exit(1)

        # Resulting orders
        nabis_orders = res["orders"]
        logger.info("Getting vehicle info from Nabis API...")
        vehicles = get_nabis_vehicles()
        logger.info("Getting driver info from Nabis API...")

        drivers = get_nabis_drivers()
        logger.info(f"Nbr of shipments found: {len(nabis_orders)}")

        # str([[x['orderNumber'],x['shipmentNumber']] for x in nabis_orders])
        ###        --          ###
        # nabis_orders.reverse()

        nabis_orders.sort(key=operator.itemgetter("orderNumber"), reverse=True)
        logger.info(
            f"Session start stats, nbr of orders: {len(nabis_orders)}, nbr of metrc templates: {len(metrc_api_find_template())} "
        )
        for nabis_order in nabis_orders:
            logger.info(
                f"Working on order ({nabis_orders.index(nabis_order)} of {len(nabis_orders)}) orders."
            )
            if duplicate_check(
                int(nabis_order["orderNumber"]), int(nabis_order["shipmentNumber"])
            ):
                logger.info(
                    f'Order {nabis_order["orderNumber"]} found in previous log. Skipping.'
                )
                counters["duplicates"] += 1
                continue
            logger.debug(f"Order {nabis_order['orderNumber']} is not a duplicate")
            start_time = time.perf_counter()

            # -----------------------------------------------------------
            #               Finding the template for order
            # -----------------------------------------------------------
            metrc_templates = metrc_api_find_template()
            template = None
            for metrc_template in metrc_templates:
                if str(nabis_order["orderNumber"]) in metrc_template["Name"]:
                    template = metrc_template
                    logger.info(
                        f"Found template for: {nabis_order['orderNumber']}, shipment: {nabis_order['shipmentNumber']}"
                    )

            if template == None:
                logger.info(
                    f'Couldnt find metrc template for order: {nabis_order["orderNumber"]}, shipment: {nabis_order["shipmentNumber"]}'
                )
                counters["template_missing"] += 1
                continue

            logger.info(
                f'##------working with order: {nabis_order["orderNumber"]}, shipment {nabis_order["shipmentNumber"]} (order {nabis_orders.index(nabis_order)} of {len(nabis_orders)} orders)  ------##'
            )

            vehicle = {}
            operator = {}
            for n in vehicles[0]["data"]["viewer"]["allVehicles"]:
                if n["id"] == nabis_order["vehicleId"]:
                    vehicle = n
            # for v in vehicles:
            #     if "allVehicles" in v["data"]["viewer"]:
            #         for n in v["data"]["viewer"]["allVehicles"]:
            #             if n["id"] == nabis_order["vehicleId"]:
            #                 vehicle = n
            for d in drivers:
                for n in d["data"]["viewer"]["allDrivers"]:
                    if n["id"] == nabis_order["driverId"]:
                        operator = n

            nabis_order_data = get_order_data(nabis_order["orderNumber"])
            if vehicle:
                vehicle["model"] = vehicle["model"].replace(vehicle["name"], "").strip()
                nabis_order_data.update({"vehicle": vehicle})
            if operator:
                nabis_order_data.update({"driver": operator})

            nabis_template_name = template["Name"]
            nabis_order_data.update({"shipment_template": nabis_template_name})

            error_log = create_metrc_manifest(
                nabis_order, nabis_order_data, template, driver
            )

            logger.debug(f"Logger dict: {error_log}")

            # log_dict = find_metrc_order(
            #     wait,
            #     driver,
            #     nabis_order,
            #     nabis_order["orderNumber"],
            #     nabis_order_data["lineItems"],
            #     nabis_order_data,
            # )
            end_time = time.perf_counter()
            logger.info(
                f"Updating the ghseet logger.. all good: {error_log['ALL_GOOD']}"
            )
            error_log.update({"Duration": end_time - start_time})
            update_log_sheet(error_log, gc)
            logger.info(f"Order {nabis_order['orderNumber']} Gsheet updating done.")

            logger.info("Moving to next order!")
        logger.info(
            f"Done: {counters['done']}; Duplicates: {counters['duplicates']}; Template missing: {counters['template_missing']}; Not done: {counters['not_done']}"
        )
        logger.info("##----------SESSION FINISHED----------##")
        session_end_time = time.perf_counter()
        session_duration = session_end_time - session_start_time

        logger.info(f"Session duration: {str(dt.timedelta(seconds=session_duration))}")
        send_slack_msg(
            f"STATS FOR CURRENT SESSION: \n\tDone: {counters['done']};\n\tDuplicates: {counters['duplicates']}; \n\tTemplate missing: {counters['template_missing']}; \n\tNot done: {counters['not_done']}; \n\tSession duration: {str(dt.timedelta(seconds=session_duration))}"
        )
        send_slack_msg("#-----⏹ {:^40s} ⏹-----#".format(f"SESSION FINISHED"))
        kill_thread(proc)

    except Exception as e:
        kill_thread(proc)
        memory_dump()
        send_slack_msg(
            f"STATS FOR CURRENT SESSION: \nDone: {counters['done']}; Duplicates: {counters['duplicates']}; Template missing: {counters['template_missing']}; Not done: {counters['not_done']}"
        )
        send_slack_msg(
            f"---------💀 SCRIPT STOPPED, ERROR: {get_traceback(e)} 💀----------##"
        )
        send_slack_msg(f"{type(e).__name__} was raised: {e}")
        logger.info(
            f"Done: {counters['done']}; Duplicates: {counters['duplicates']}; Template missing: {counters['template_missing']}; Not done: {counters['not_done']}"
        )
        logger.error(get_traceback(e))
        email_logger = define_email_logger()

        fl_name = str(dt.datetime.today()).replace(":", ".")
        try:
            driver.save_screenshot(f"{paths['errors_sc']}Error_{fl_name}.jpg")
        except UnboundLocalError:
            pass
        email_logger.error(get_traceback(e))
        logger.error(get_traceback(e))


if __name__ == "__main__":
    main()
