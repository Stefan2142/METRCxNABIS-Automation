import datetime as dt
from bs4 import BeautifulSoup
import time
import re
import json
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
)
from creds import credentials


GARDEN_OF_WEEDEN_METRC = "C11-0000340-LIC"
NABITWO_METRC = "C11-0001274-LIC"

WAREHOUSE = NABITWO_METRC
routes = []


def find_metrc_order(
    wait, driver, nabis_shipment, nabis_order_id, nabis_order_line_items, nabis_order
):
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
    driver.find_element(by=By.CLASS_NAME, value="k-icon.k-i-filter").click()

    # Filter input box, clear and input order number
    wait.until(
        EC.visibility_of_element_located((By.XPATH, '//*[@title="Filter Criteria"]'))
    )
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
    results = driver.find_elements(by=By.CLASS_NAME, value= "k-grid-norecords.grid-no-data")
    if len(results) > 0:
        print(f"Results not found for order {nabis_order_id}, {len(results)} {results}")
        return False
    else:
        print(f"Results for order: {nabis_order_id} found!")

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
    print("Exited while loop!")

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
        except:
            pass

    proc_template(
        driver, nabis_order_id, nabis_order_line_items, nabis_order, nabis_shipment
    )


def proc_template(
    driver, nabis_order_id, nabis_order_line_items, nabis_order, nabis_shipment
):
    from creds import matching_attrs

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
            "total": x["pricePerUnit"] * x["quantity"],
        }
        for x in nabis_order_line_items
    }
    try:
        metrc_transfer_type = Select(
            driver.find_element(
                By.XPATH, value='//*[@ng-model="destination.TransferTypeId"]'
            )
        ).first_selected_option.text
    except:
        metrc_transfer_type = ""

    
    def update_log(key,error_msg):
        nonlocal log_dict
        log_dict.update(
            {
                matching_attrs[key][error_msg]: matching_attrs[
                    key
                ][error_msg].format(
                    matching_attrs[key]["metrc"]["data"],
                    matching_attrs[key]["nabis"]["data"],
                )
            }
        )
    
    matching_attrs["license"]["metrc"]["data"] = driver.find_element(
        by=By.XPATH, value=matching_attrs["license"]["metrc_key"]
    ).get_attribute("value")
    matching_attrs["license"]["nabis"]["data"] = nabis_order["siteLicenseNum"]

    """C11-0001274-LIC - Nabitwo
        C11-0000340-LIC - Garden of Weeden
        C11-0000825-LIC - Cannex / 4Front"""
    if (
        matching_attrs["license"]["metrc"]["data"].strip()
        != matching_attrs["license"]["nabis"]["data"].strip()
    ):
        if matching_attrs["license"]["metrc"]["data"].strip() not in [
            "C11-0001274-LIC",
            "C11-0000340-LIC",
            "C11-0000825-LIC",
        ]:
            log_dict.update(
                {
                    matching_attrs["license"]["error_incorrect_key"]: matching_attrs[
                        "license"
                    ]["error_incorrect_msg"].format(
                        matching_attrs["license"]["metrc"]["data"],
                        matching_attrs["license"]["nabis"]["data"],
                    )
                }
            )

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
        ] = f"{nabis_order['driver']['firstName']} {nabis_order['driver']['lastName']}"
    except TypeError:
        matching_attrs["driver"]["nabis"]["data"] = f""
        log_dict.update(
            {
                matching_attrs["driver"]["error_missing_key"]: matching_attrs["driver"][
                    "error_missing_msg"
                ].format(
                    matching_attrs["driver"]["metrc"]["data"],
                    matching_attrs["driver"]["nabis"]["data"],
                )
            }
        )

    if (
        "".join(matching_attrs["driver"]["metrc"]["data"].split()).lower()
        != "".join(matching_attrs["driver"]["nabis"]["data"].split()).lower()
    ):
        update_log('driver', 'error_incorrect_key')
        log_dict.update(
            {
                matching_attrs["driver"]["error_incorrect_key"]: matching_attrs[
                    "driver"
                ]["error_incorrect_msg"].format(
                    "".join(matching_attrs["driver"]["metrc"]["data"].split()).lower(),
                    "".join(matching_attrs["driver"]["nabis"]["data"].split()).lower(),
                )
            }
        )

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
        log_dict.update(
            {
                matching_attrs["driver_id"]["error_missing_key"]: matching_attrs[
                    "driver_id"
                ]["error_missing_msg"].format(
                    matching_attrs["driver_id"]["metrc"]["data"],
                    matching_attrs["driver_id"]["nabis"]["data"],
                )
            }
        )

    if (
        matching_attrs["driver_id"]["metrc"]["data"]
        != matching_attrs["driver_id"]["nabis"]["data"]
    ):
        log_dict.update(
            {
                matching_attrs["driver_id"]["error_incorrect_key"]: matching_attrs[
                    "driver_id"
                ]["error_incorrect_msg"].format(
                    matching_attrs["driver_id"]["metrc"]["data"],
                    matching_attrs["driver_id"]["nabis"]["data"],
                )
            }
        )

    # VEHICLE MAKE
    matching_attrs["vehicle_make"]["metrc"]["data"] = driver.find_element(
        by=By.XPATH, value=matching_attrs["vehicle_make"]["metrc_key"]
    ).get_attribute("value")
    try:
        matching_attrs["vehicle_make"]["nabis"]["data"] = nabis_order["vehicle"]["make"]
    except TypeError:
        matching_attrs["vehicle_make"]["nabis"]["data"] = ""
        log_dict.update(
            {
                matching_attrs["vehicle_make"]["error_missing_key"]: matching_attrs[
                    "vehicle_make"
                ]["error_missing_msg"].format(
                    matching_attrs["vehicle_make"]["metrc"]["data"],
                    matching_attrs["vehicle_make"]["nabis"]["data"],
                )
            }
        )

    if (
        matching_attrs["vehicle_make"]["metrc"]["data"].strip()
        != matching_attrs["vehicle_make"]["nabis"]["data"].strip()
    ):
        log_dict.update(
            {
                matching_attrs["vehicle_make"]["error_incorrect_key"]: matching_attrs[
                    "vehicle_make"
                ]["error_incorrect_msg"].format(
                    matching_attrs["vehicle_make"]["metrc"]["data"],
                    matching_attrs["vehicle_make"]["nabis"]["data"],
                )
            }
        )

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
        log_dict.update(
            {
                matching_attrs["vehicle_model"]["error_missing_key"]: matching_attrs[
                    "vehicle_model"
                ]["error_missing_msg"].format(
                    matching_attrs["vehicle_model"]["metrc"]["data"],
                    matching_attrs["vehicle_model"]["nabis"]["data"],
                )
            }
        )

    if (
        matching_attrs["vehicle_model"]["nabis"]["data"]
        not in matching_attrs["vehicle_model"]["metrc"]["data"]
    ):
        log_dict.update(
            {
                matching_attrs["vehicle_model"]["error_incorrect_key"]: matching_attrs[
                    "vehicle_model"
                ]["error_incorrect_msg"].format(
                    matching_attrs["vehicle_model"]["metrc"]["data"],
                    matching_attrs["vehicle_model"]["nabis"]["data"],
                )
            }
        )

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
        log_dict.update(
            {
                matching_attrs["vehicle_plate"]["error_missing_key"]: matching_attrs[
                    "vehicle_plate"
                ]["error_missing_msg"].format(
                    matching_attrs["vehicle_plate"]["metrc"]["data"],
                    matching_attrs["vehicle_plate"]["nabis"]["data"],
                )
            }
        )

    if (
        matching_attrs["vehicle_plate"]["metrc"]["data"]
        != matching_attrs["vehicle_plate"]["nabis"]["data"]
    ):
        log_dict.update(
            {
                matching_attrs["vehicle_plate"]["error_incorrect_key"]: matching_attrs[
                    "vehicle_plate"
                ]["error_incorrect_msg"].format(
                    matching_attrs["vehicle_plate"]["metrc"]["data"],
                    matching_attrs["vehicle_plate"]["nabis"]["data"],
                )
            }
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
    if any([route_search_str in x for x in routes]):
        matching_attrs["route"]["metrc"]["data"] = [
            x for x in routes if route_search_str in x
        ][0]

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
            print("Number of packages not the same!!!")
    else:
        print("Number of packages is the same!!!")

    for i in nabis_packages.keys():
        if i != "SKIP":
            if not metrc_only_tags.get(i):
                # tag is missing
                log_dict.update(
                    {
                        "MissingPackageTag": f"Tag exists in nabis but not in metrc template. NabisTagId: '{i}'"
                    }
                )

            else:
                if nabis_packages[i]["quantity"] != metrc_only_tags[i]["quantity"]:

                    log_dict.update(
                        {
                            "WrongQuantity": f"Incorrect quantity; Metrc: {metrc_only_tags[i]['quantity']}, Nabis: {nabis_packages[i]['quantity']}"
                        }
                    )
                else:
                    print("Quantities good;")

                ### AKO JE TRANSFER A NE WHOLESALE MANIFEST

                if nabis_packages[i]["total"] != metrc_only_tags[i]["WholesalePrice"]:
                    if metrc_transfer_type != "Transfer":
                        log_dict.update(
                            {
                                "WrongPrice": f"Incorrect price; Metrc: {metrc_only_tags[i]['WholesalePrice']}, Nabis: {nabis_packages[i]['total']}"
                            }
                        )
                    else:
                        print(
                            "Price missing on metrc side but template type is Transfer"
                        )
                else:
                    print("Prices good;")
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

    if log_dict:
        print(json.dumps(log_dict, indent=2))
        log_dict.update({"ALL_GOOD": "FALSE"})
        # finish_template_get_manifest(driver, WAREHOUSE, nabis_order)
    else:
        print("---All good!---")
        log_dict.update({"ALL_GOOD": "TRUE"})
        finish_template_get_manifest(driver, WAREHOUSE, nabis_order)

    log_dict.update({"Order": str(nabis_order_id)})
    log_dict.update(
        {
            "Shipment": list(
                filter(
                    lambda word: word[0] == "#",
                    nabis_order["shipment_template"].split(),
                )
            )[0]
        }
    )
    log_dict.update(
        {
            "Date": dt.datetime.strftime(
                dt.datetime.now(dt.datetime.now().astimezone().tzinfo),
                "%Y-%m-%dT%H:%M%z",
            )
        }
    )
    update_log_sheet(log_dict)

    # o = get_order_data(nabis_order["orderNumber"])
    # transfer = view_metrc_transfer(nabis_order['id'])
    # transfer_id = [
    #     x["id"]
    #     for x in transfer["data"]["getMetrcTransfers"]
    #     if nabis_order["template_name"] == x["metrcTransferTemplateName"]
    # ][0]

    # upload_manifest_pdf(transfer_id, "name.pdf")

    driver.get(
        f"https://ca.metrc.com/industry/{WAREHOUSE}/transfers/licensed/templates"
    )
    return log_dict


def main():
    global routes
    routes = get_spreadsheet_routes()
    driver = get_driver()
    wait = WebDriverWait(driver, 180)

    ### Login directives for METRC ###
    # driver.get("https://ca.metrc.com/")
    driver.get(
        f"https://ca.metrc.com/industry/{WAREHOUSE}/transfers/licensed/templates"
    )
    try:
        driver.find_element(by=By.XPATH, value='//*[@id="username"]').send_keys(
            credentials["metrc"]["un"]
        )
    except:
        # LOG HERE
        print("Couldnt find username box")

    driver.find_element(by=By.XPATH, value='//*[@id="password"]').send_keys(
        credentials["metrc"]["pwd"]
    )
    driver.find_element(by=By.XPATH, value='//*[@id="login_button"]').click()
    driver.get(
        f"https://ca.metrc.com/industry/{WAREHOUSE}/transfers/licensed/templates"
    )

    cookie_list = driver.get_cookies()
    soup = BeautifulSoup(driver.page_source, "html.parser")
    metrc_api_verification_token = (
        str(soup(text=re.compile(r"ApiVerificationToken")))
        .split("X-Metrc-LicenseNumber")[0]
        .split("ApiVerificationToken")[-1]
        .split("'")[2]
    )
    metrc_cookie = "".join(
        [
            f"MetrcRequestToken={x['value']}"
            for x in cookie_list
            if x["name"] == "MetrcRequestToken"
        ]
    )
    metrc_cookie += "".join(
        [
            f";MetrcSessionTime={x['value']}"
            for x in cookie_list
            if x["name"] == "MetrcSessionTime"
        ]
    )
    metrc_cookie += "".join(
        [f";MetrcAuth={x['value']}" for x in cookie_list if x["name"] == "MetrcAuth"]
    )

    ###             --             ###

    ### Get list of orders ###
    # Passing a tomorrow's date (month-day-year): '03-04-2022"'
    tomorrow = dt.datetime.strftime(
        dt.datetime.now() + dt.timedelta(days=1), "%m-%d-%Y"
    )
    print(f"Working with date {tomorrow}")
    # Get nabis tracker shipments
    res = get_tracker_shipments(tomorrow)

    # total number of pages
    total_num_pages = res["total_num_pages"]

    # Total number of resulting orders for given query
    total_num_items = res["total_num_items"]
    if total_num_items == 0:
        print(f"No orders to work on for date {tomorrow}")

    # Resulting orders
    nabis_orders = res["orders"]
    vehicles = get_vehicles()
    drivers = get_drivers()

    ###        --          ###
    for nabis_order in nabis_orders:
        template_req = find_template(
            str(nabis_order["orderNumber"]),
            metrc_api_verification_token,
            metrc_cookie,
            WAREHOUSE,
        )
        if template_req["Data"] == []:
            print(f'Couldnt find metrc template for {nabis_order["orderNumber"]}')
            continue
        else:
            # We always want the first result(0th) from the template search
            nabis_template_name = template_req["Data"][0]["Name"]

        print(json.dumps(nabis_order, indent=2))
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

        print(f'working with {nabis_order["orderNumber"]}')
        nabis_order["orderNumber"]
        nabis_order["order"][
            "id"
        ]  # - this should be usefor later querying of metrc transfers [NABIS site]
        nabis_order["order"]["lineItems"]
        nabis_order["order"]["lineItems"]

        nabis_order_data = get_order_data(nabis_order["orderNumber"])
        if vehicle:
            nabis_order_data.update({"vehicle": vehicle})
        if operator:
            nabis_order_data.update({"driver": operator})

        nabis_order_data.update({"shipment_template": nabis_template_name})

        find_metrc_order(
            wait,
            driver,
            nabis_order,
            nabis_order["orderNumber"],
            nabis_order_data["lineItems"],
            nabis_order_data,
        )
        print("yey!")
        # continue
    exit(1)

    # For the last part, Nabis (pdf upload)
    o = get_order_data(nabis_order["orderNumber-"])
    transfer = view_metrc_transfer(o["id"])
    # Get id of transfer for which we generated manifest from a found template
    transfer_id = [
        x["id"]
        for x in transfer["data"]["getMetrcTransfers"]
        if nabis_order["template_name"] == x["metrcTransferTemplateName"]
    ][0]
    upload_manifest_pdf(transfer_id, "name.pdf")


if __name__ == "__main__":
    main()
