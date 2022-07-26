import datetime as dt
import time
import json
import os
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
import glob
from api_calls import (
    get_tracker_shipments,
    get_order_data,
    get_nabis_drivers,
    get_nabis_vehicles,
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
    update_log_sheet,
    define_default_logger,
    define_email_logger,
    get_cookie_and_token,
    get_traceback,
    duplicate_check,
    send_slack_msg,
    memory_dump,
    slack_idle_notif_thr,
    metrc_get_facilities,
    get_cwd_files,
    metrc_driver_login,
)
from creds.creds import credentials
from config import paths, WAREHOUSES, nabis_warehouse_licenses
import gspread
import ctypes
import inquirer

counters = {"done": 0, "duplicates": 0, "template_missing": 0, "not_done": 0}

recipient_data = ""
routes = []
logger = define_default_logger()
email_logger = define_email_logger()
WAREHOUSE = {}


def create_metrc_manifest(nabis_order, nabis_order_data, template, driver):
    global recipient_data
    global WAREHOUSE

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
    if (id_response == "errors") or (id_response == False):
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


def main():
    global routes
    global logger
    global counters
    global recipient_data
    global WAREHOUSE
    import operator

    questions = [
        inquirer.List(
            "warehouse",
            message="Pick warehouse for script to work with, current answer:",
            choices=["Garden of Weeden", "Nabitwo", "Front Commerce"],
        ),
    ]
    answer = inquirer.prompt(questions)
    WAREHOUSE = WAREHOUSES[answer["warehouse"]]
    gc = gspread.service_account(
        filename="./creds/emailsending-325211-e5456e88f282.json"
    )

    import threading

    proc = threading.Thread(target=slack_idle_notif_thr, args=(gc,), daemon=True)
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

    # Remove previously downloaded pdfs
    files = glob.glob(f"{paths['pdfs']}*.pdf")
    for f in files:
        os.remove(f)

    session_start_time = time.perf_counter()
    try:
        logger.info(
            f"##----------SESSION STARTED with warehouse: {WAREHOUSE['name']}----------##"
        )

        send_slack_msg(
            "#-----▶ {:^40s} ▶-----#".format(
                f"SESSION STARTED BY USER: {os.getenv('CLIENTNAME')}, for the warehouse: {WAREHOUSE['name']}"
            )
        )

        logger.info("Getting routes from gsheet...")
        routes = get_spreadsheet_routes(gc)
        logger.info("Initializing Chrome WebDriver...")
        driver = get_driver()
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
        nabis_tracker_shipments = get_tracker_shipments(tomorrow)

        if nabis_tracker_shipments == False:
            logger.info("Error while getting shipments from Nabis. Exiting...")
            send_slack_msg(f"Error while getting shipments from Nabis. Exiting...")
            exit(1)

        # total number of pages
        total_num_pages = nabis_tracker_shipments["total_num_pages"]

        # Total number of resulting shipments for given query
        total_num_items = nabis_tracker_shipments["total_num_items"]
        if total_num_items == 0:
            logger.info(f"No shipments to work on for date {tomorrow}")
            send_slack_msg(f"No shipments to work on for date {tomorrow}")
            exit(1)

        # Resulting shipments
        nabis_shipments = nabis_tracker_shipments["shipments"]
        logger.info("Getting vehicle info from Nabis API...")
        vehicles = get_nabis_vehicles()
        logger.info("Getting driver info from Nabis API...")

        drivers = get_nabis_drivers()
        logger.info(f"Nbr of shipments found: {len(nabis_shipments)}")

        # nabis_shipments.reverse()

        nabis_shipments.sort(key=operator.itemgetter("orderNumber"), reverse=True)
        logger.info(
            f"Session start stats, nbr of shipments: {len(nabis_shipments)}, nbr of metrc templates: {len(metrc_api_find_template())} "
        )
        for nabis_shipment in nabis_shipments:
            logger.info(
                f"Working on shipment ({nabis_shipments.index(nabis_shipment)} of {len(nabis_shipments)}) shipment."
            )
            if duplicate_check(
                int(nabis_shipment["orderNumber"]),
                int(nabis_shipment["shipmentNumber"]),
            ):
                logger.info(
                    f'Order {nabis_shipment["orderNumber"]} found in previous log. Skipping.'
                )
                counters["duplicates"] += 1
                continue
            logger.debug(f"Order {nabis_shipment['orderNumber']} is not a duplicate")
            start_time = time.perf_counter()

            # -----------------------------------------------------------
            #               Finding the template for order
            # -----------------------------------------------------------
            metrc_templates = metrc_api_find_template()
            template = None
            for metrc_template in metrc_templates:
                if str(nabis_shipment["orderNumber"]) in metrc_template["Name"]:
                    template = metrc_template
                    logger.info(
                        f"Found template for order: {nabis_shipment['orderNumber']}, shipment: {nabis_shipment['shipmentNumber']}"
                    )

            if template == None:
                logger.info(
                    f'Couldnt find metrc template for order: {nabis_shipment["orderNumber"]}, shipment: {nabis_shipment["shipmentNumber"]}'
                )
                counters["template_missing"] += 1
                continue

            logger.info(
                f'##------working with order: {nabis_shipment["orderNumber"]}, shipment {nabis_shipment["shipmentNumber"]} (shipment {nabis_shipments.index(nabis_shipment)} of {len(nabis_shipments)} shipment)  ------##'
            )

            vehicle = {}
            operator = {}
            for n in vehicles[0]["data"]["viewer"]["allVehicles"]:
                if n["id"] == nabis_shipment["vehicleId"]:
                    vehicle = n
            # for v in vehicles:
            #     if "allVehicles" in v["data"]["viewer"]:
            #         for n in v["data"]["viewer"]["allVehicles"]:
            #             if n["id"] == nabis_shipment["vehicleId"]:
            #                 vehicle = n
            for d in drivers:
                for n in d["data"]["viewer"]["allDrivers"]:
                    if n["id"] == nabis_shipment["driverId"]:
                        operator = n

            nabis_order_data = get_order_data(nabis_shipment["orderNumber"])
            if vehicle:
                vehicle["model"] = vehicle["model"].replace(vehicle["name"], "").strip()
                nabis_order_data.update({"vehicle": vehicle})
            if operator:
                nabis_order_data.update({"driver": operator})

            nabis_template_name = template["Name"]
            nabis_order_data.update({"shipment_template": nabis_template_name})

            error_log = create_metrc_manifest(
                nabis_shipment, nabis_order_data, template, driver
            )

            logger.debug(f"Logger dict: {error_log}")

            end_time = time.perf_counter()
            logger.info(
                f"Updating the ghseet logger.. all good: {error_log['ALL_GOOD']}"
            )
            error_log.update({"Duration(S)": end_time - start_time})
            update_log_sheet(error_log, gc)
            logger.info(f"Order {nabis_shipment['orderNumber']} Gsheet updating done.")

            logger.info("Moving to next shipment!")
        logger.info(
            f"Done: {counters['done']}; Duplicates: {counters['duplicates']}; Template missing: {counters['template_missing']}; Not done: {counters['not_done']}"
        )
        logger.info("##----------SESSION FINISHED----------##")
        session_end_time = time.perf_counter()
        session_duration = session_end_time - session_start_time

        logger.info(
            f"Session duration(S): {str(dt.timedelta(seconds=session_duration))}"
        )
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
