from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import selenium.common.exceptions
import datetime as dt
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import json
import gspread
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

WAREHOUSE = GARDEN_OF_WEEDEN_METRC
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
    results = driver.find_elements_by_class_name("k-grid-norecords.grid-no-data")
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
    soup = BeautifulSoup(driver.page_source, "html.parser")
    script_element = soup.find(text=re.compile("repeaterData"))
    raw_json = script_element[
        script_element.find("JSON.parse") : script_element.rfind("x7d'),")
    ]
    json_str = bytes(raw_json.encode("utf8"))[:-1:].decode("unicode-escape")
    json_str = json_str + "}"
    json_dict = json.loads(json_str[12:])

    wrongs = {}
    log_dict = {}
    log_dict.update({"Order": str(nabis_order_id)})
    log_dict.update(
        {
            "Date": dt.datetime.strftime(
                dt.datetime.now(dt.datetime.now().astimezone().tzinfo),
                "%Y-%m-%dT%H:%M%z",
            )
        }
    )

    metrc_packages = [
        x for x in json_dict["Packages"] if str(nabis_order_id) in x["Note"]
    ]
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

    if any([None == x for x in list(nabis_packages.keys())]):
        wrongs.update({"PackageMissing": "One line item doesnt have metrc tag"})
        log_dict.update({"PackageMissing": "One line item doesnt have metrc tag"})

    matching_attrs = {
        "license": {
            "metrc_xpath": '//*[@ng-model="destination.RecipientId"]',
            "nabis_key": "siteLicenseNum",
        }
    }
    metrc_destination_license = driver.find_element(
        by=By.XPATH, value='//*[@ng-model="destination.RecipientId"]'
    ).get_attribute("value")
    nabis_destination_license = nabis_order["siteLicenseNum"]

    if metrc_destination_license.strip() != nabis_destination_license.strip():
        """C11-0001274-LIC - Nabitwo
        C11-0000340-LIC - Garden of Weeden
        C11-0000825-LIC - Cannex / 4Front"""

        if metrc_destination_license.strip() not in [
            "C11-0001274-LIC",
            "C11-0000340-LIC",
            "C11-0000825-LIC",
        ]:
            wrongs.update(
                {
                    "IncorrectLicense": f"Licenses doesnt match metrc: {metrc_destination_license} vs nabis: {nabis_destination_license}"
                }
            )
            log_dict.update(
                {
                    "IncorrectLicense": f"Licenses doesnt match metrc: {metrc_destination_license} vs nabis: {nabis_destination_license}"
                }
            )

    metrc_planned_route = driver.find_element(
        by=By.NAME, value="model[0][Destinations][0][PlannedRoute]"
    ).get_attribute("value")

    # OVO MORA BITI +1 dand od TRENUTNOG

    metrc_est_departure = dt.datetime.strptime(
        json_dict["Details"][0]["Destinations"][0]["EstimatedDepartureDateTime"],
        "%Y-%m-%dT%H:%M:%S.%f",
    )

    metrc_est_arrival = dt.datetime.strptime(
        json_dict["Details"][0]["Destinations"][0]["EstimatedArrivalDateTime"],
        "%Y-%m-%dT%H:%M:%S.%f",
    )

    if metrc_est_departure.date() != metrc_est_arrival.date():
        wrongs.update(
            {
                "IncorrectDates": f"Metrc depart. and arrival dates are different; Depart: {metrc_est_departure.date()}, Arrival: {metrc_est_arrival.date()}"
            }
        )
        log_dict.update(
            {
                "IncorrectDates": f"Metrc depart. and arrival dates are different; Depart: {metrc_est_departure.date()}, Arrival: {metrc_est_arrival.date()}"
            }
        )
    dt.datetime.now().date()
    metrc_est_departure.date() - dt.timedelta(days=1)

    ### DRIVER
    metrc_driver = json_dict["Details"][0]["Destinations"][0]["Transporters"][0][
        "DriverName"
    ]
    try:
        nabis_driver = (
            f"{nabis_order['driver']['firstName']} {nabis_order['driver']['lastName']}"
        )
    except TypeError:
        nabis_driver = f""
        wrongs.update(
            {
                "MissingDriverNabis": f"Driver name is missing; Metrc: {''.join(metrc_driver.split()).lower()}, Nabis: {nabis_driver}"
            }
        )
        log_dict.update(
            {
                "MissingDriverNabis": f"Driver name is missing; Metrc: {''.join(metrc_driver.split()).lower()}, Nabis: {nabis_driver}"
            }
        )

    if "".join(metrc_driver.split()).lower() != "".join(nabis_driver.split()).lower():
        wrongs.update(
            {
                "IncorrectDriver": f"Driver name incorrect; Metrc: {''.join(metrc_driver.split()).lower()}, Nabis: {''.join(nabis_driver.split()).lower()}"
            }
        )
        log_dict.update(
            {
                "IncorrectDriver": f"Driver name incorrect; Metrc: {''.join(metrc_driver.split()).lower()}, Nabis: {''.join(nabis_driver.split()).lower()}"
            }
        )

    metrc_driver_id = driver.find_element(
        by=By.XPATH,
        value='//*[@ng-model="transporterDetail.DriverOccupationalLicenseNumber"]',
    ).get_attribute("value")
    try:
        nabis_driver_id = nabis_order["driver"]["driversLicense"]
    except TypeError:
        nabis_driver_id = ""
        wrongs.update(
            {
                "MissingDriverIdNabis": f"Driver ID missing; Metrc: {metrc_driver_id}, Nabis: {nabis_driver_id}"
            }
        )
        log_dict.update(
            {
                "MissingDriverIdNabis": f"Driver ID missing; Metrc: {metrc_driver_id}, Nabis: {nabis_driver_id}"
            }
        )

    if metrc_driver_id != nabis_driver_id:
        wrongs.update(
            {
                "IncorrectDriverId": f"Driver ID incorrect; Metrc: {metrc_driver_id}, Nabis: {nabis_driver_id}"
            }
        )
        log_dict.update(
            {
                "IncorrectDriverId": f"Driver ID incorrect; Metrc: {metrc_driver_id}, Nabis: {nabis_driver_id}"
            }
        )

    # metrc_driver_drivers_lic = driver.find_element(
    #     by=By.XPATH, value='//*[@ng-model="transporterDetail.DriverLicenseNumber"]'
    # ).get_attribute("value")

    ### VEHICLE
    metrc_vehicle_make = driver.find_element(
        by=By.XPATH, value='//*[@ng-model="transporterDetail.VehicleMake"]'
    ).get_attribute("value")
    try:
        nabis_vehicle_make = nabis_order["vehicle"]["make"]
    except TypeError:
        nabis_vehicle_make = ""
        wrongs.update(
            {
                "MissingVehicleMake(Nabis)": f"Missing vehicle maker; Metrc {metrc_vehicle_make}, Nabis: {nabis_vehicle_make}"
            }
        )
        log_dict.update(
            {
                "MissingVehicleMake(Nabis)": f"Missing vehicle maker; Metrc {metrc_vehicle_make}, Nabis: {nabis_vehicle_make}"
            }
        )

    if metrc_vehicle_make.strip() != nabis_vehicle_make.strip():
        wrongs.update(
            {
                "IncorrectVehicleMake": f"Incorrect vehicle maker; Metrc {metrc_vehicle_make}, Nabis: {nabis_vehicle_make}"
            }
        )
        log_dict.update(
            {
                "IncorrectVehicleMake": f"Incorrect vehicle maker; Metrc {metrc_vehicle_make}, Nabis: {nabis_vehicle_make}"
            }
        )

    metrc_vehicle_model = driver.find_element(
        by=By.XPATH, value='//*[@ng-model="transporterDetail.VehicleModel"]'
    ).get_attribute("value")

    try:
        nabis_vehicle_model = nabis_order["vehicle"]["name"]
    except TypeError:
        nabis_vehicle_model = ""
        wrongs.update(
            {
                "MissingVehicleMake": f"Missing vehicle maker; Metrc {metrc_vehicle_model}, Nabis: {nabis_vehicle_model}"
            }
        )
        log_dict.update(
            {
                "MissingVehicleMake": f"Missing vehicle maker; Metrc {metrc_vehicle_model}, Nabis: {nabis_vehicle_model}"
            }
        )

    if nabis_vehicle_model not in metrc_vehicle_model:
        wrongs.update(
            {
                "IncorrectVehicleModel": f"Incorrect vehicle model; Metrc {metrc_vehicle_model}, Nabis: {nabis_vehicle_model}"
            }
        )
        log_dict.update(
            {
                "IncorrectVehicleModel": f"Incorrect vehicle model; Metrc {metrc_vehicle_model}, Nabis: {nabis_vehicle_model}"
            }
        )

    metrc_license_plate = driver.find_element(
        by=By.XPATH,
        value='//*[@ng-model="transporterDetail.VehicleLicensePlateNumber"]',
    ).get_attribute("value")
    try:
        nabis_license_plate = nabis_order["vehicle"]["licensePlate"]
    except TypeError:
        nabis_license_plate = ""
        wrongs.update(
            {
                "MissingVehicleMake": f"Missing vehicle plate; Metrc: {metrc_license_plate}, Nabis: {nabis_license_plate}"
            }
        )
        log_dict.update(
            {
                "MissingVehicleMake": f"Missing vehicle plate; Metrc: {metrc_license_plate}, Nabis: {nabis_license_plate}"
            }
        )

    if metrc_license_plate != nabis_license_plate:
        wrongs.update(
            {
                "IncorrectVehicleMake": f"Incorrect vehicle plate; Metrc: {metrc_license_plate}, Nabis: {nabis_license_plate}"
            }
        )
        log_dict.update(
            {
                "IncorrectVehicleMake": f"Incorrect vehicle plate; Metrc: {metrc_license_plate}, Nabis: {nabis_license_plate}"
            }
        )

    if wrongs:
        print(f"WRONGS : {wrongs}")

    addresses = (
        metrc_planned_route.replace(str(nabis_order_id), "")
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
        route = [x for x in routes if route_search_str in x][0]

    else:
        wrongs.update(
            {
                "CantFindRoute": f"Cant find route in the sheet for planned route (metrc): {metrc_planned_route}"
            }
        )
        log_dict.update(
            {
                "CantFindRoute": f"Cant find route in the sheet for planned route (metrc): {metrc_planned_route}"
            }
        )

    # metrc_only_tags = {
    #     x["Label"]: {"quantity": x["Quantity"], "WholesalePrice": x["WholesalePrice"]}
    #     for x in metrc_packages
    # }
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

    if len(nabis_packages) != len(metrc_only_tags):
        if "SKIP" not in nabis_packages.keys():
            wrongs.update(
                {
                    "IncorrectPkgNbr": f"Mismatch of number of packages between metrc and nabis; Metrc: {len(metrc_only_tags)}, Nabis: {len(nabis_packages)}"
                }
            )
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
                wrongs.update(
                    {
                        "MissingPackageTag": f"Tag exists in nabis but not in metrc template. TagId: '{i}'"
                    }
                )
                log_dict.update(
                    {
                        "MissingPackageTag": f"Tag exists in nabis but not in metrc template. TagId: '{i}'"
                    }
                )

            else:
                if nabis_packages[i]["quantity"] != metrc_only_tags[i]["quantity"]:
                    wrongs.update(
                        {
                            "WrongQuantity": f"Incorrect quantity; Metrc: {metrc_only_tags[i]['quantity']}, Nabis: {nabis_packages[i]['quantity']}"
                        }
                    )
                    log_dict.update(
                        {
                            "WrongQuantity": f"Incorrect quantity; Metrc: {metrc_only_tags[i]['quantity']}, Nabis: {nabis_packages[i]['quantity']}"
                        }
                    )
                else:
                    print("Quantities good;")

                if nabis_packages[i]["total"] != metrc_only_tags[i]["WholesalePrice"]:
                    wrongs.update(
                        {
                            "WrongPrice": f"Incorrect price ; Metrc: {metrc_only_tags[i]['WholesalePrice']}, Nabis: {nabis_packages[i]['total']}"
                        }
                    )
                    log_dict.update(
                        {
                            "WrongPrice": f"Incorrect price; Metrc: {metrc_only_tags[i]['WholesalePrice']}, Nabis: {nabis_packages[i]['total']}"
                        }
                    )
                else:
                    print("Prices good;")

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
    ).send_keys(route)
    time.sleep(1)

    if wrongs:
        print(json.dumps(wrongs, indent=2))
        log_dict.update({"ALL_GOOD": "FALSE"})
        finish_template_get_manifest(driver, WAREHOUSE, nabis_order)
    else:
        print("---All good!---")
        log_dict.update({"ALL_GOOD": "TRUE"})
        finish_template_get_manifest(driver, WAREHOUSE, nabis_order)

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
            str(nabis_order["orderNumber"]), metrc_api_verification_token, metrc_cookie
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
