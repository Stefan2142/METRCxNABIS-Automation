from matplotlib.pyplot import get
import requests
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
import selenium.common.exceptions
import os
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

from routines import get_cwd_files, nabis_login, get_driver, get_spreadsheet_routes
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
            ).click()
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

    metrc_destination_license = driver.find_element(
        by=By.XPATH, value='//*[@ng-model="destination.RecipientId"]'
    ).get_attribute("value")
    nabis_destination_license = nabis_order["siteLicenseNum"]

    if metrc_destination_license.strip() != nabis_destination_license.strip():
        wrongs.update(
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
    dt.datetime.now().date()
    metrc_est_departure.date() - dt.timedelta(days=1)

    ### DRIVER
    metrc_driver = json_dict["Details"][0]["Destinations"][0]["Transporters"][0][
        "DriverName"
    ]
    nabis_driver = (
        f"{nabis_order['driver']['firstName']} {nabis_order['driver']['lastName']}"
    )

    if "".join(metrc_driver.split()).lower() != "".join(nabis_driver.split()).lower():
        wrongs.update(
            {
                "IncorrectDriver": f"Driver name incorrect; Metrc: {''.join(metrc_driver.split()).lower()}, Nabis: {''.join(nabis_driver.split()).lower()}"
            }
        )

    metrc_driver_id = driver.find_element(
        by=By.XPATH,
        value='//*[@ng-model="transporterDetail.DriverOccupationalLicenseNumber"]',
    ).get_attribute("value")

    nabis_driver_id = nabis_order["driver"]["driversLicense"]

    if metrc_driver_id != nabis_driver_id:
        wrongs.update(
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
    nabis_vehicle_make = nabis_order["vehicle"]["make"]

    if metrc_vehicle_make != nabis_vehicle_make:
        wrongs.update(
            {
                "IncorrectVehicleMake": f"Incorrect vehicle maker; Metrc {metrc_vehicle_make}, Nabis: {nabis_vehicle_make}"
            }
        )

    metrc_vehicle_model = driver.find_element(
        by=By.XPATH, value='//*[@ng-model="transporterDetail.VehicleModel"]'
    ).get_attribute("value")
    nabis_vehicle_model = nabis_order["vehicle"]["name"]
    if nabis_vehicle_model not in metrc_vehicle_model:
        wrongs.update(
            {
                "IncorrectVehicleModel": f"Incorrect vehicle model; Metrc {metrc_vehicle_model}, Nabis: {nabis_vehicle_model}"
            }
        )

    metrc_license_plate = driver.find_element(
        by=By.XPATH,
        value='//*[@ng-model="transporterDetail.VehicleLicensePlateNumber"]',
    ).get_attribute("value")
    nabis_license_plate = nabis_order["vehicle"]["licensePlate"]
    if metrc_license_plate != nabis_license_plate:
        wrongs.update(
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

    metrc_only_tags = {
        x["Label"]: {"quantity": x["Quantity"], "WholesalePrice": x["WholesalePrice"]}
        for x in metrc_packages
    }
    if len(nabis_packages) != len(metrc_only_tags):
        wrongs.update(
            {
                "IncorrectPkgNbr": f"Mismatch of number of packages between metrc and nabis; Metrc: {len(metrc_only_tags)}, Nabis: {len(nabis_packages)}"
            }
        )
        print("Number of packages not the same!!!")
    else:
        print("Number of packages is the same!!!")

    for i in nabis_packages.keys():
        if not metrc_only_tags.get(i):
            # tag is missing
            wrongs.update(
                {
                    "MissingPackageTag": f"Tag exists in nabis but not in metrc template: {i}"
                }
            )

        else:
            if nabis_packages[i]["quantity"] != metrc_only_tags[i]["quantity"]:
                wrongs.update(
                    {
                        "WrongQuantity": f"Incorrect quantity; Metrc: {metrc_only_tags[i]['quantity']}, Nabis: {nabis_packages[i]['quantity']}"
                    }
                )
            else:
                print("Quantities good;")

            if nabis_packages[i]["total"] != metrc_only_tags[i]["WholesalePrice"]:
                wrongs.update(
                    {
                        "WrongPrice": f"Incorrect price; Metrc: {metrc_only_tags[i]['total']}, Nabis: {nabis_packages[i]['WholesalePrice']}"
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

    if wrongs:
        print(json.dumps(wrongs, indent=2))
    else:
        print("---All good!---")

    # for i in nabis_order_line_items:
    #     if i["metrcPackageTag"] in metrc_only_tags:
    #         print(
    #             i["metrcPackageTag"],
    #             metrc_only_tags[i["metrcPackageTag"]],
    #         )
    #     else:
    #         print(
    #             f"Nabis tag {i['metrcPackageTag']} cant be found on metrc side (metrc_only_tags: [{','.join(metrc_only_tags)}])"
    #         )

    ### SUBMIT
    driver.find_element(
        by=By.XPATH, value='//*[@id="addedit-transfer_form"]/div/button[1]'
    ).text

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

    driver.find_element(
        by=By.NAME, value="model[0][Destinations][0][PlannedRoute]"
    ).get_attribute("value")

    time.sleep(0.3)
    return True


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
        dt.datetime.now() + dt.timedelta(days=0), "%m-%d-%Y"
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
        # order_data["lineItems"]
        # order_data["lineItems"][0]["quantity"]
        # order_data["lineItems"][0]["pricePerUnit"]
        # order_data["lineItems"][0]["metrcPackageTag"]
        # order_data["lineItems"][0]["isSample"]
        # if order_data['lineItems'][0]['metrcPackageTag'] == None:...

        # find_template('144583', metrc_api_verification_token, metrc_cookie)

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
    ### AFTER SUBMITTING A TEMPLATE
    # For licensed transfer (not the same as templates for transfer), this is 2nd step
    driver.get(f"https://ca.metrc.com/industry/{WAREHOUSE}/transfers/licensed")

    driver.find_element_by_id("outgoing-tab").click()

    WebDriverWait(driver, 15).until(
        EC.invisibility_of_element_located(
            (By.CLASS_NAME, "tab-select-one text-center")
        )
    )
    rows = driver.find_elements(
        by=By.CLASS_NAME, value="k-master-row.grid-editable-row"
    )
    for row in rows:
        supa = BeautifulSoup(row.get_attribute("innerHTML"), "html.parser")

        # MANIFEST ID
        supa.find_all("td", {"role": "gridcell"})[0].text.strip()
        # NAME
        supa.find_all("td", {"role": "gridcell"})[-3].text.strip()
        # DATE
        supa.find_all("td", {"role": "gridcell"})[-2].text.strip()

    # In order to download pdf of a manifest:
    # https://ca.metrc.com/reports/transfers/{WAREHOUSE}/manifest?id=0003165145
    # (just replace the id with the manifest id)

    ###

    # wait.until(
    #         EC.visibility_of_element_located(
    #             (By.CLASS_NAME, 'icon-box__wrapper')
    #         )
    #     )
    """
    var link = document.createElement("a");
        link.href = 'https://ca.metrc.com/reports/transfers/{}/manifest?id=3165145';
        link.download = "name.pdf";
        link.click();
    """.format(
        WAREHOUSE
    )
    list_of_pdf = get_cwd_files()
    o = get_order_data(142358)
    transfer = view_metrc_transfer(o["id"])
    transfer["data"]["getMetrcTransfers"][0]["id"]
    upload_manifest_pdf(transfer["data"]["getMetrcTransfers"][0]["id"], "name.pdf")
    soup = BeautifulSoup(driver.page_source, "html.parser")


if __name__ == "__main__":
    main()
