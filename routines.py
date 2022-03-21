import gspread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import os, time
from creds import credentials
from api_calls import upload_manifest_pdf, upload_manifest_id, view_metrc_transfer


def waiting_fnc(driver, path):
    """Fnc utilizing while loop which gives a correctly waiting function
    (waiting for an element to appear). Selenium's waiting methods arent reliable enough;


    Args:
        driver (webdriver): driver for browser
        path (str): path
    """


def check_prices():
    pass


def update_log_sheet(log_dict):
    # Update logging gsheet file
    gc = gspread.service_account(filename="./emailsending-325211-e5456e88f282.json")
    sh = gc.open_by_url(
        "https://docs.google.com/spreadsheets/d/1LkP08iIUIZyRz-_C45AJ0FvRJuwGK_SzuZylfNMrAuE"
    )
    wks = sh.worksheet("Logs")
    sheet_df = pd.DataFrame(wks.get_all_records())

    df_dict = pd.DataFrame([log_dict])
    output = pd.concat([sheet_df, df_dict], ignore_index=True)
    output.fillna("", inplace=True)
    output["WrongPrice"] = output["WrongPrice"].apply(str)
    output["WrongQuantity"] = output["WrongQuantity"].apply(str)
    output["MissingPackageTag"] = output["MissingPackageTag"].apply(str)

    wks.update([output.columns.values.tolist()] + output.values.tolist())


def finish_template_get_manifest(driver, WAREHOUSE, nabis_order):

    ### SUBMIT BUTTON
    driver.find_element(
        by=By.XPATH, value='//*[@id="addedit-transfer_form"]/div/button[1]'
    ).click()
    # Waiting for the Transfer pop-up to close itself
    bool = True
    while bool:
        try:
            time.sleep(0.5)

            driver.find_element(
                by=By.NAME,
                value="model[0][Destinations][0][Transporters][0][TransporterDetails][0][VehicleMake]",
            )
        except:
            bool = False
            pass
    ### AFTER SUBMITTING A TEMPLATE
    # For licensed transfer (not the same as templates for transfer), this is 2nd step
    # Remove Template
    driver.find_element(by=By.XPATH, value="//*[@title='Discontinue']").click()
    alert_obj = driver.switch_to.alert
    alert_obj.accept()
    time.sleep(1)
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
    current_files = len(get_cwd_files())
    for row in rows:
        soup = BeautifulSoup(row.get_attribute("innerHTML"), "html.parser")

        # MANIFEST ID
        manifest_id = soup.find_all("td", {"role": "gridcell"})[0].text.strip()
        # NAME
        employee = soup.find_all("td", {"role": "gridcell"})[-3].text.strip()
        # DATE
        manifest_date_created = soup.find_all("td", {"role": "gridcell"})[
            -2
        ].text.strip()
        if employee == "Aleksandar Plavljanic":
            driver.execute_script(
                """
            var link = document.createElement("a");
                link.href = 'https://ca.metrc.com/reports/transfers/{}/manifest?id={}';
                link.download = "name.pdf";
                link.click();
            """.format(
                    WAREHOUSE, manifest_id
                )
            )
            # Here we wait when the file gets downloaed
            while current_files == len(get_cwd_files()):
                pass
            time.sleep(1)
            list_of_pdf = get_cwd_files()
            list_of_pdf = filter(lambda pdf: ".pdf" in pdf, list_of_pdf)
            list_of_pdf = list(list_of_pdf)

            # o = get_order_data(nabis_order["orderNumber"])
            transfer = view_metrc_transfer(nabis_order["id"])
            transfer_id = [
                x["id"]
                for x in transfer["data"]["getMetrcTransfers"]
                if nabis_order["shipment_template"] == x["metrcTransferTemplateName"]
            ][0]
            print(f"list_of_pdfs: {list_of_pdf}")
            print(f"File to be uploaded {list_of_pdf[0]}")
            pdf_response = upload_manifest_pdf(transfer_id, list_of_pdf[0])
            id_response = upload_manifest_id(transfer_id, manifest_id)
            if "errors" in pdf_response:
                print(
                    f'Error while uploading manifest pdf {transfer_id}, order: {nabis_order["id"]}'
                )
            if "errors" in id_response:
                print(
                    f'Error while uploading manifest id number {transfer_id}, order {nabis_order["id"]}'
                )

            return manifest_id
            # For the last part, Nabis (pdf upload)
            o = get_order_data(142358)
            transfer = view_metrc_transfer(o["id"])
            transfer["data"]["getMetrcTransfers"][0]["id"]
            upload_manifest_pdf(
                transfer["data"]["getMetrcTransfers"][0]["id"], "name.pdf"
            )
            [os.remove(x) for x in list_of_pdf]


"""
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
        pass"""
###
# wait.until(
#         EC.visibility_of_element_located(
#             (By.CLASS_NAME, 'icon-box__wrapper')
#         )
#     )


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
    # chrome_options.add_argument("--window-size=1536,865")

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
