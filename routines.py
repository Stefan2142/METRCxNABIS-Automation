import gspread
from selenium import webdriver
from creds import credentials
import pandas as pd
import os


def get_spreadsheet_routes():
    gc = gspread.service_account(filename="./emailsending-325211-e5456e88f282.json")

    sh = gc.open_by_url(
        "https://docs.google.com/spreadsheets/d/1gGctslxmXIO490qnKPN2SbWZV2ZLT7Z3zIpxQo19us8"
    )

    known_sheets = ["LA routes", "OAK routes"]
    routes = []
    for sheet in known_sheets:
        wks = sh.worksheet(sheet)
        routes_df = pd.DataFrame(wks.get_all_records())

        routes.extend(routes_df[routes_df.columns[0]].tolist())

    return routes


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

    driver.find_element(
        by=By.XPATH, value='//*[@id="sign-in"]/div[1]/div/div[1]/input'
    ).send_keys(credentials["nabis"]["un"])

    driver.find_element(
        by=By.XPATH, value='//*[@id="sign-in"]/div[2]/div/div[1]/input'
    ).send_keys(credentials["nabis"]["pwd"])

    driver.find_element(by=By.XPATH, value='//*[@id="sign-in"]/button[2]').click()

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
    return list_of_files
