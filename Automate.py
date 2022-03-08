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
from api_calls import NABITWO, get_tracker_shipments, get_order_data

from creds import credentials

GARDEN_OF_WEEDEN_METRC = "C11-0000340-LIC"
NABITWO_METRC = "C11-0001274-LIC"

WAREHOUSE = NABITWO_METRC


def get_driver():
    chrome_options = webdriver.ChromeOptions()
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "download.default_directory": os.getcwd(),
        "download.prompt_for_download": False,
        "profile.default_content_setting_values.geolocation": 2,
    }

    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--start-maximized")
    # chrome_options.add_argument("--headless")

    driver = webdriver.Chrome(
        executable_path="./chromedriver.exe", chrome_options=chrome_options
    )
    return driver


def nabis_login(driver):
    driver.get("https://app.getnabis.com/nabione-inc-deliveries/app/dashboard")

    driver.find_element_by_xpath(
        '//*[@id="sign-in"]/div[1]/div/div[1]/input'
    ).send_keys(credentials["nabis"]["un"])

    driver.find_element_by_xpath(
        '//*[@id="sign-in"]/div[2]/div/div[1]/input'
    ).send_keys(credentials["nabis"]["pwd"])

    driver.find_element_by_xpath('//*[@id="sign-in"]/button[2]').click()

    # Get on Admin Shipments Tracker Page
    driver.get(
        "https://app.getnabis.com/nabione-inc-deliveries/app/admin-shipment-tracker"
    )
    return driver


def get_cwd_files():
    list_of_files = filter(
        lambda x: os.path.isfile(os.path.join(os.getcwd(), x)), os.listdir(os.getcwd())
    )
    list_of_files = sorted(
        list_of_files, key=lambda x: os.path.getmtime(os.path.join(os.getcwd(), x))
    )
    list_of_files.reverse()  # 0th element is the newest


def find_metrc_order(wait, driver, order_id, nabis_order_line_items, nabis_order):

    # Click on three dots for filtering
    # Here we have 6 elements with the same class name. Its
    # actually 6 columns that allow filtering. We always need the first one,
    # 'Template' column. So by sing find_element instead of find_elements..
    # we are clicking on the first(0th) element in that array

    # Click on three dots

    try:
        driver.find_element_by_class_name("k-header-column-menu").click()
    except selenium.common.exceptions.ElementClickInterceptedException:
        time.sleep(0.3)
        wait.until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "k-loading-text"))
        )
        driver.find_element_by_class_name("k-header-column-menu").click()

    # Click on 'Filter' sub-menu
    time.sleep(0.5)
    driver.find_element_by_class_name("k-icon.k-i-filter").click()

    # Filter input box, clear and input order number
    wait.until(
        EC.visibility_of_element_located((By.XPATH, '//*[@title="Filter Criteria"]'))
    )
    driver.find_element_by_xpath('//*[@title="Filter Criteria"]').clear()
    driver.find_element_by_xpath('//*[@title="Filter Criteria"]').send_keys(
        str(order_id)
    )
    # driver.find_element_by_xpath('//*[@title="Filter Criteria"]').send_keys("141200")

    # Click on 'Filter' button
    driver.find_element_by_class_name("k-button.k-primary").click()
    wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "k-loading-text")))
    time.sleep(0.5)

    # If search result is empty
    # If <list> results is empty, there are no results for a given order
    results = driver.find_elements_by_class_name("k-grid-norecords.grid-no-data")
    if len(results) > 0:
        print(f"Results not found for order {order_id}, {len(results)} {results}")
        return False
    else:
        print(f"Results for order: {order_id} found!")
        # return True

        # While loop for waiting for appearance of 'Use' button
        # Click on 'USE' button
        # use_button.click()
        bool = True
        while bool:
            try:
                time.sleep(0.5)
                driver.find_element_by_class_name(
                    "k-button.k-button-icontext.grid-row-button.k-grid-Use"
                ).click()
                bool = False
            except:
                pass
    print("Exited while loop!")
    ### MISSING LOGIC FOR PICKING A CORRECT ROW ###

    # wait.until(
    #     EC.visibility_of_element_located(
    #         (By.CLASS_NAME, "k-button.k-button-icontext.grid-row-button.k-grid-Use")
    #     )
    # )

    # wait.until(
    #     EC.element_to_be_clickable(
    #         (By.CLASS_NAME, "k-button.k-button-icontext.grid-row-button.k-grid-Use")
    #     )
    # )

    # wait.until(
    #     EC.presence_of_element_located(
    #         (By.CLASS_NAME, "k-button.k-button-icontext.grid-row-button.k-grid-Use")
    #     )
    # )

    # Wait for Transfer window to open after clicking 'Use'
    # This one takes around a minute or so

    # FOR WORKING WITH GIGANTIC FILE:
    # with open('hex.txt', 'r') as f:
    #     r_f = f.read()

    # res_s = bytes(r_f[:], 'ascii').decode('unicode-escape')
    # with open('hex2_res.txt', 'w') as f: f.write(res_s)
    # res_s_json = json.loads(res_s)
    # paketi = [x for x in res_s_json['Packages'] if '142852' in x['Note']]

    bool = True
    while bool:
        try:
            time.sleep(0.5)
            driver.find_element_by_name(
                "model[0][Destinations][0][Transporters][0][TransporterDetails][0][VehicleMake]"
            ).click()
            bool = False
        except:
            pass

    # try:
    #     wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "k-widget k-window")))
    # except:
    #     wait.until(EC.presence_of_element_located((By.CLASS_NAME, "k-widget k-window")))
    # Direktno iz browser-a

    soup = BeautifulSoup(driver.page_source, "html.parser")
    script_element = soup.find(text=re.compile("repeaterData"))
    raw_json = script_element[
        script_element.find("JSON.parse") : script_element.rfind("x7d'),")
    ]
    json_str = bytes(raw_json.encode("utf8"))[:-1:].decode("unicode-escape")
    json_str = json_str + "}"
    json_dict = json.loads(json_str[12:])
    metrc_packages = [x for x in json_dict["Packages"] if str(order_id) in x["Note"]]

    metrc_destination_license = json_dict["Facilities"][
        str(json_dict["Details"][0]["Destinations"][0]["RecipientId"])
    ]["LicenseNumber"]
    metrc_planned_route = json_dict["Details"][0]["Destinations"][0]["PlannedRoute"]
    metrc_est_departure = json_dict["Details"][0]["Destinations"][0][
        "EstimatedDepartureDateTime"
    ]
    metrc_est_arrival = json_dict["Details"][0]["Destinations"][0][
        "EstimatedArrivalDateTime"
    ]
    metrc_driver = json_dict["Details"][0]["Destinations"][0]["Transporters"][0][
        "DriverName"
    ]
    metrc_vehicle_model = json_dict["Details"][0]["Destinations"][0]["Transporters"][0][
        "VehicleModel"
    ]

    # nabis_order["lineItems"]
    # nabis_order["lineItems"][0]["quantity"]
    # nabis_order["lineItems"][0]["pricePerUnit"]
    # nabis_order["lineItems"][0]["metrcPackageTag"]
    # nabis_order["lineItems"][0]["isSample"]
    # if nabis_order['lineItems'][0]['metrcPackageTag'] == None:...

    import usaddress

    addr_parse = usaddress.parse(metrc_planned_route)

    metrc_tags = [
        {
            "license_number": x["ItemFromFacilityLicenseNumber"],
            "tag": x["Label"],
            "quantity": x["Quantity"],
        }
        for x in metrc_packages
    ]

    metrc_only_tags = [x["tag"] for x in metrc_tags]
    if len(nabis_order_line_items) != len(metrc_only_tags):
        pass

    for i in nabis_order_line_items:
        if i["metrcPackageTag"] in metrc_only_tags:
            print(
                i["metrcPackageTag"],
                metrc_only_tags[metrc_only_tags.index(i["metrcPackageTag"])],
            )
        else:
            print(
                f"Nabis tag {i['metrcPackageTag']} cant be found on metrc side (metrc_only_tags: [{','.join(metrc_only_tags)}])"
            )
    driver.find_element_by_name("model[0][Destinations][0][PlannedRoute]").click()

    driver.find_element_by_name(
        "model[0][Destinations][0][PlannedRoute]"
    ).get_attribute("value")
    time.sleep(0.3)
    return True
    soup = BeautifulSoup(driver.page_source(), "html.parser")
    package_rows = soup.find_all("tr", {"class": "offset1 ng-scope"})


def main():
    driver = get_driver()
    wait = WebDriverWait(driver, 180)

    ### Login directives for METRC ###
    # driver.get("https://ca.metrc.com/")
    driver.get(
        f"https://ca.metrc.com/industry/{WAREHOUSE}/transfers/licensed/templates"
    )
    try:
        driver.find_element_by_xpath('//*[@id="username"]').send_keys(
            credentials["metrc"]["un"]
        )
    except:
        # LOG HERE
        print("Couldnt find username box")

    driver.find_element_by_xpath('//*[@id="password"]').send_keys(
        credentials["metrc"]["pwd"]
    )
    driver.find_element_by_xpath('//*[@id="login_button"]').click()
    driver.get(
        f"https://ca.metrc.com/industry/{WAREHOUSE}/transfers/licensed/templates"
    )
    ###             --             ###

    ### Get list of orders ###
    # Passing a tomorrow's date (month-day-year): '03-04-2022"'
    tomorrow = dt.datetime.strftime(
        dt.datetime.now() + dt.timedelta(days=1), "%m-%d-%Y"
    )
    print(f"Working with date {tomorrow}")
    res = get_tracker_shipments(tomorrow)

    # total number of pages
    total_num_pages = res["total_num_pages"]

    # Total number of resulting orders for given query
    total_num_items = res["total_num_items"]
    if total_num_items == 0:
        print(f"No orders to work on for date {tomorrow}")

    # Resulting orders
    orders = res["orders"]
    ###        --          ###
    for order in orders:
        print(f'working with {order["orderNumber"]}')
        order["orderNumber"]
        order["order"][
            "id"
        ]  # - this should be usefor later querying of metrc transfers [NABIS site]
        order["order"]["lineItems"]
        order["order"]["lineItems"]

        order_data = get_order_data(order["orderNumber"])
        # order_data["lineItems"]
        # order_data["lineItems"][0]["quantity"]
        # order_data["lineItems"][0]["pricePerUnit"]
        # order_data["lineItems"][0]["metrcPackageTag"]
        # order_data["lineItems"][0]["isSample"]
        # if order_data['lineItems'][0]['metrcPackageTag'] == None:...
        find_metrc_order(
            wait, driver, order["orderNumber"], order_data["lineItems"], order_data
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
    soup = BeautifulSoup(driver.page_source, "html.parser")


if __name__ == "__main__":
    main()
