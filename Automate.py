import datetime as dt
from bs4 import BeautifulSoup
import operator
import time
import re
import json
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import selenium.common.exceptions
from selenium.webdriver.support.ui import Select
from api_calls import (
    get_tracker_shipments,
    get_order_data,
    get_drivers,
    get_vehicles,
    find_template,
    view_metrc_transfer,
    upload_manifest_pdf,
    upload_manifest_id,
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
)
from creds import credentials, WAREHOUSE
import gspread

routes = []
logger = define_default_logger()
email_logger = define_email_logger()


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
                time.sleep(0.5)
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
    from creds import matching_attrs

    global logger
    soup = BeautifulSoup(driver.page_source, "html.parser")
    script_element = soup.find(text=re.compile("repeaterData"))
    raw_json = script_element[
        script_element.find("JSON.parse") : script_element.rfind("x7d'),")
    ]
    json_str = bytes(raw_json.encode("utf8"))[:-1:].decode("unicode-escape")
    json_str = json_str + "}"
    json_dict = json.loads(json_str[12:])

    log_dict = {}

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
        log_dict.update({"UnreadableTransferType": "TRUE"})

    def update_log(key, error_type, error_msg):
        nonlocal log_dict
        log_dict.update(
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
        if (str(matching_attrs[key]["metrc"]["data"]).strip() == "temp") and (
            str(matching_attrs[key]["nabis"]["data"]).strip() == ""
        ):
            return False
        elif str(matching_attrs[key]["metrc"]["data"]).strip() == "temp":
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
            return True
        else:
            return True

    matching_attrs["license"]["metrc"]["data"] = driver.find_element(
        by=By.XPATH, value=matching_attrs["license"]["metrc_key"]
    ).get_attribute("value")
    matching_attrs["license"]["nabis"]["data"] = nabis_order["siteLicenseNum"]

    """C11-0001274-LIC - Nabitwo
        C11-0000340-LIC - Garden of Weeden
        C11-0000825-LIC - Cannex / 4Front"""
    if (
        matching_attrs["license"]["metrc"]["data"].strip().lower()
        != matching_attrs["license"]["nabis"]["data"].strip().lower()
    ):
        # If its internal transfer, they dont need to match
        if matching_attrs["license"]["metrc"]["data"].strip() not in [
            "C11-0001274-LIC",
            "C11-0000340-LIC",
            "C11-0000825-LIC",
        ]:
            update_log("license", "error_incorrect_key", "error_incorrect_msg")

    # Check if its internal transfer
    if matching_attrs["license"]["metrc"]["data"].strip() not in [
        "C11-0001274-LIC",
        "C11-0000340-LIC",
        "C11-0000825-LIC",
    ]:
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

    dt.datetime.now().date()
    matching_attrs["est_departure_date"]["metrc"]["data"].date() - dt.timedelta(days=1)

    # DRIVER MATCHING
    matching_attrs["driver"]["metrc"]["data"] = json_dict["Details"][0]["Destinations"][
        0
    ]["Transporters"][0]["DriverName"]
    try:
        matching_attrs["driver"]["nabis"][
            "data"
        ] = f"{nabis_order['driver']['firstName'].strip()} {nabis_order['driver']['lastName'].strip()}"
    except TypeError:
        matching_attrs["driver"]["nabis"]["data"] = f""
        if not temp_none_check("driver"):
            update_log("driver", "error_missing_key", "error_missing_msg")

    if (
        "".join(matching_attrs["driver"]["metrc"]["data"].split()).lower()
        != "".join(matching_attrs["driver"]["nabis"]["data"].split()).lower()
    ):
        if not temp_none_check("driver"):
            update_log("driver", "error_incorrect_key", "error_incorrect_msg")

    # DRIVER'S ID matching
    matching_attrs["driver_id"]["metrc"]["data"] = driver.find_element(
        by=By.XPATH,
        value=matching_attrs["driver_id"]["metrc_key"],
    ).get_attribute("value")

    try:
        matching_attrs["driver_id"]["nabis"]["data"] = nabis_order["driver"][
            "driversLicense"
        ]
    except TypeError:
        matching_attrs["driver_id"]["nabis"]["data"] = ""
        if not temp_none_check("driver_id"):
            update_log("driver_id", "error_missing_key", "error_missing_msg")

    if (
        matching_attrs["driver_id"]["metrc"]["data"]
        != matching_attrs["driver_id"]["nabis"]["data"]
    ):
        if not temp_none_check("driver_id"):
            update_log("driver_id", "error_incorrect_key", "error_incorrect_msg")

    # VEHICLE MAKE
    matching_attrs["vehicle_make"]["metrc"]["data"] = driver.find_element(
        by=By.XPATH, value=matching_attrs["vehicle_make"]["metrc_key"]
    ).get_attribute("value")
    try:
        matching_attrs["vehicle_make"]["nabis"]["data"] = nabis_order["vehicle"]["make"]
    except TypeError:
        matching_attrs["vehicle_make"]["nabis"]["data"] = ""
        if not temp_none_check("vehicle_make"):
            update_log("vehicle_make", "error_missing_key", "error_missing_msg")

    if (
        matching_attrs["vehicle_make"]["metrc"]["data"].strip()
        != matching_attrs["vehicle_make"]["nabis"]["data"].strip()
    ):
        if not temp_none_check("vehicle_make"):
            update_log("vehicle_make", "error_incorrect_key", "error_incorrect_msg")

    # VEHICLE MODEL
    matching_attrs["vehicle_model"]["metrc"]["data"] = driver.find_element(
        by=By.XPATH, value=matching_attrs["vehicle_model"]["metrc_key"]
    ).get_attribute("value")

    try:
        matching_attrs["vehicle_model"]["nabis"]["data"] = nabis_order["vehicle"][
            "name"
        ]
    except TypeError:
        matching_attrs["vehicle_model"]["nabis"]["data"] = ""
        if not temp_none_check("vehicle_model"):
            update_log("vehicle_model", "error_missing_key", "error_missing_msg")

    if (
        matching_attrs["vehicle_model"]["nabis"]["data"]
        not in matching_attrs["vehicle_model"]["metrc"]["data"]
    ):
        if not temp_none_check("vehicle_model"):
            update_log("vehicle_model", "error_incorrect_key", "error_incorrect_msg")

    # License plate
    matching_attrs["vehicle_plate"]["metrc"]["data"] = driver.find_element(
        by=By.XPATH,
        value=matching_attrs["vehicle_plate"]["metrc_key"],
    ).get_attribute("value")
    try:
        matching_attrs["vehicle_plate"]["nabis"]["data"] = nabis_order["vehicle"][
            "licensePlate"
        ]
    except TypeError:
        matching_attrs["vehicle_plate"]["nabis"]["data"] = ""
        if not temp_none_check("vehicle_plate"):
            update_log("vehicle_plate", "error_missing_key", "error_missing_msg")

    if (
        matching_attrs["vehicle_plate"]["metrc"]["data"].strip().lower()
        != matching_attrs["vehicle_plate"]["nabis"]["data"].strip().lower()
    ):
        if not temp_none_check("vehicle_plate"):
            update_log("vehicle_plate", "error_incorrect_key", "error_incorrect_msg")

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
        log_dict.update(
            {"MissingChildPackageTag": "One line item doesnt have metrc tag"}
        )

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
        # EST Departure time
        driver.find_element(
            By.XPATH, value='//*[@ng-model="destination.EstimatedDepartureDateTime"]'
        ).clear()
        driver.find_element(
            By.XPATH, value='//*[@ng-model="destination.EstimatedDepartureDateTime"]'
        ).send_keys(
            dt.datetime.strftime(dt.datetime.now() + dt.timedelta(days=1), "%m/%d/%Y")
        )
        # EST Arrival time
        driver.find_element(
            By.XPATH, value='//*[@ng-model="destination.EstimatedArrivalDateTime"]'
        ).clear()
        driver.find_element(
            By.XPATH, value='//*[@ng-model="destination.EstimatedArrivalDateTime"]'
        ).send_keys(
            dt.datetime.strftime(dt.datetime.now() + dt.timedelta(days=1), "%m/%d/%Y")
        )

    for i in nabis_packages.keys():
        if i != "SKIP":
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

                if nabis_packages[i]["total"] != metrc_only_tags[i]["WholesalePrice"]:
                    # if (metrc_transfer_type == 'Wholesale Transfer') and (all_metrc_prices_none == False):

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

    # CHECK FOR TEMP VALUES
    """Temp values are present in these fields:
        Driver name,
        Employee ID,
        Driver's Lic. No.,
        Vehicle Make
        Vehicle Model
        License Plate
    """

    # temp_checker([metrc_driver,metrc_driver_id, metrc_driver_id, metrc_vehicle_make, metrc_vehicle_model, metrc_license_plate])

    # def temp_checker(l):
    #     for i in l:
    #         if i == "temp":
    #             pass

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

    if log_dict:
        logger.info(f"Log for order: {nabis_order_id}:")
        logger.info(json.dumps(log_dict, indent=2))
        log_dict.update({"InternalTransfer": internal_transfer})
        log_dict.update({"TransferType": metrc_transfer_type})
        log_dict.update({"ALL_GOOD": "FALSE"})
        log_dict.update({"ManifestId": ""})

        # finish_template_get_manifest(driver, WAREHOUSE['license'], nabis_order)
    else:
        if empty_prices_checker(driver):
            logger.info(f"Log for order: {nabis_order_id}:")
            log_dict.update({"PricesEmpty": "TRUE"})
            log_dict.update({"InternalTransfer": internal_transfer})
            log_dict.update({"TransferType": metrc_transfer_type})
            log_dict.update({"ALL_GOOD": "FALSE"})
            send_slack_msg(f"\t ❌ Order: {nabis_order_id} failed. Check gsheet log.")

        else:
            logger.info(
                f"---All checks good: {nabis_order_id} / ({shipment}) uploading pdf and id!---"
            )
            log_dict.update({"TransferType": metrc_transfer_type})

            finish_status = finish_template_get_manifest(
                driver, WAREHOUSE["license"], nabis_order, logger
            )
            if finish_status["pdf_response"] == False:
                log_dict.update(
                    {"ALL_GOOD": "FALSE - Template regsitered. PDF not updated"}
                )
                send_slack_msg(
                    f"\t ❌ rder: {nabis_order_id} registered. Failure at manifest pdf upload. Do it manually. (Manifest nbr: {finish_status['manifest_id']})"
                )

            elif finish_status["id_response"] == False:
                log_dict.update(
                    {"ALL_GOOD": "FALSE - Template regsitered. Manifest ID not updated"}
                )
                send_slack_msg(
                    f"\t ❌ rder: {nabis_order_id} registered. Failure at manifest id upload. Do it manually. (Manifest nbr: {finish_status['manifest_id']})"
                )
            else:
                log_dict.update({"ALL_GOOD": "TRUE"})

            log_dict.update({"InternalTransfer": internal_transfer})
            log_dict.update({"ManifestId": finish_status["manifest_id"]})

    log_dict.update({"Order": str(nabis_order_id)})
    log_dict.update({"Shipment": str(shipment)})
    log_dict.update({"PkgNbr": len(nabis_packages)})
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

    driver.get(
        f"https://ca.metrc.com/industry/{WAREHOUSE['license']}/transfers/licensed/templates"
    )
    return log_dict


def main():
    global routes
    global logger
    import operator
    gc = gspread.service_account(filename="./emailsending-325211-e5456e88f282.json")
    try:
        logger.info("##----------SESSION STARTED----------##")

        send_slack_msg(
            "#-----▶ {:^40s} ▶-----#".format(
                f"SESSION STARTED BY USER: {os.getenv('CLIENTNAME')}"
            )
        )

        logger.info("Getting routes from gsheet...")
        routes = get_spreadsheet_routes(gc)
        logger.info("Initializing Chrome WebDriver...")
        driver = get_driver()
        wait = WebDriverWait(driver, 180)

        ### Login directives for METRC ###
        driver.get(
            f"https://ca.metrc.com/industry/{WAREHOUSE['license']}/transfers/licensed/templates"
        )
        try:
            driver.find_element(by=By.XPATH, value='//*[@id="username"]').send_keys(
                credentials["metrc"]["un"]
            )
        except:
            # LOG HERE
            logger.error("Couldnt find username box")

        driver.find_element(by=By.XPATH, value='//*[@id="password"]').send_keys(
            credentials["metrc"]["pwd"]
        )
        driver.find_element(by=By.XPATH, value='//*[@id="login_button"]').click()
        driver.get(
            f"https://ca.metrc.com/industry/{WAREHOUSE['license']}/transfers/licensed/templates"
        )

        metrc_auth = get_cookie_and_token(driver)

        # Getting date for nabis shipment query
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
            exit(1)

        # total number of pages
        total_num_pages = res["total_num_pages"]

        # Total number of resulting orders for given query
        total_num_items = res["total_num_items"]
        if total_num_items == 0:
            logger.info(f"No orders to work on for date {tomorrow}")

        # Resulting orders
        nabis_orders = res["orders"]
        logger.info("Getting vehicle info from Nabis API...")
        vehicles = get_vehicles()
        logger.info("Getting driver info from Nabis API...")

        drivers = get_drivers()
        logger.info(f"Nbr of shipments found: {len(nabis_orders)}")

        # str([[x['orderNumber'],x['shipmentNumber']] for x in nabis_orders])
        ###        --          ###
        # nabis_orders.reverse()

        nabis_orders.sort(key=operator.itemgetter("orderNumber"), reverse=True)
        for nabis_order in nabis_orders:
            if duplicate_check(gc, int(nabis_order["orderNumber"])):
                logger.info(
                    f'Order {nabis_order["orderNumber"]} found in previous log. Skipping.'
                )
                continue
            logger.debug(f"Order {nabis_order['orderNumber']} is not a duplicate")
            start_time = time.perf_counter()
            template_req = find_template(
                str(nabis_order["orderNumber"]),
                metrc_auth["token"],
                metrc_auth["cookie"],
                WAREHOUSE["license"],
            )
            try:
                if template_req["Data"] == []:
                    logger.info(
                        f'Couldnt find metrc template for order: {nabis_order["orderNumber"]}, shipment: {nabis_order["shipmentNumber"]}'
                    )
                    continue
                else:
                    # We always want the first result(0th) from the template search
                    nabis_template_name = template_req["Data"][0]["Name"]
            except KeyError:
                metrc_auth = get_cookie_and_token(driver)
                template_req = find_template(
                    str(nabis_order["orderNumber"]),
                    metrc_auth["token"],
                    metrc_auth["cookie"],
                    WAREHOUSE["license"],
                )
                if template_req["Data"] == []:
                    logger.info(
                        f'Couldnt find metrc template for order: {nabis_order["orderNumber"]}, shipment: {nabis_order["shipmentNumber"]}'
                    )
                    continue

            if str(nabis_order["shipmentNumber"]) not in nabis_template_name:
                logger.info(
                    f'Order template found but shipment numbers are not the same: {nabis_order["shipmentNumber"]} vs metrc {nabis_template_name}, skipping.'
                )
                continue

            logger.info(
                f'##------working with order: {nabis_order["orderNumber"]}, shipment {nabis_order["shipmentNumber"]}------##'
            )
            # logger.info(json.dumps(nabis_order, indent=2))

            vehicle = {}
            operator = {}
            for v in vehicles:
                if "allVehicles" in v["data"]["viewer"]:
                    for n in v["data"]["viewer"]["allVehicles"]:
                        if n["id"] == nabis_order["vehicleId"]:
                            vehicle = n
            for d in drivers:
                for n in d["data"]["viewer"]["allDrivers"]:
                    if n["id"] == nabis_order["driverId"]:
                        operator = n

            nabis_order_data = get_order_data(nabis_order["orderNumber"])
            if vehicle:
                nabis_order_data.update({"vehicle": vehicle})
            if operator:
                nabis_order_data.update({"driver": operator})

            nabis_order_data.update({"shipment_template": nabis_template_name})

            log_dict = find_metrc_order(
                wait,
                driver,
                nabis_order,
                nabis_order["orderNumber"],
                nabis_order_data["lineItems"],
                nabis_order_data,
            )
            end_time = time.perf_counter()
            logger.info("Updating the ghseet logger..")
            log_dict.update({"Duration(S)": end_time - start_time})
            update_log_sheet(log_dict, gc)
            logger.info(f"Order {nabis_order['orderNumber']} Gsheet updating done.")

            logger.info("Moving to next order!")
            # continue
        logger.info("##----------SESSION FINISHED----------##")

        send_slack_msg("#-----⏹ {:^15s} ⏹-----#".format(f"SESSION FINISHED"))
    except Exception as e:
        # raise
        logger.error(get_traceback(e))
        email_logger = define_email_logger()
        send_slack_msg(
            f"---------💀 SCRIPT STOPPED, ERROR: {get_traceback(e)} 💀----------##"
        )
        fl_name = str(dt.datetime.today()).replace(":", ".")
        try:
            driver.save_screenshot(f"./Logs/Error_{fl_name}.jpg")
        except UnboundLocalError:
            pass
        email_logger.error(get_traceback(e))
        raise


if __name__ == "__main__":
    main()
