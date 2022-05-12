from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from pathlib import Path
import pandas as pd
import sys
import json
import datetime as dt
import os, time
import re
import logging
import logging.handlers
from pythonjsonlogger import jsonlogger
from creds import credentials, slack_token
from config import paths, urls
from api_calls import (
    upload_manifest_pdf,
    upload_manifest_id,
    view_metrc_transfer,
    upload_order_note,
)
import traceback
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from Screenshot import Screenshot_Clipping
from tenacity import retry, wait_fixed

# def define_download_folder():
#     # Unused
#     downloadDir = f"{os.getcwd()}//downloads//"
#     # Make sure path exists.
#     Path(downloadDir).mkdir(parents=True, exist_ok=True)

#     # Set Preferences.
#     preferences = {
#         "download.default_directory": downloadDir,
#         "download.prompt_for_download": False,
#         "directory_upgrade": True,
#         "safebrowsing.enabled": True,
#     }

#     chromeOptions = webdriver.ChromeOptions()
#     chromeOptions.add_argument("--window-size=1480x560")
#     chromeOptions.add_experimental_option("prefs", preferences)

#     preferences = {
#         "profile.default_content_settings.popups": 0,
#         "download.default_directory": os.getcwd() + os.path.sep,
#         "directory_upgrade": True,
#     }


#     chrome_options.add_experimental_option("prefs", preferences)


def waiting_fnc(driver, path):
    """Fnc utilizing while loop which gives a correctly waiting function
    (waiting for an element to appear). Selenium's waiting methods arent reliable enough;


    Args:
        driver (webdriver): driver for browser
        path (str): path
    """
    """
    driver.find_element_by_id("user-alerts").get_attribute("innerHTML")
'\n\n\n\n\n<div class="alert alert-error"><a class="close" data-dismiss="alert">×</a><p>Execution Timeout Expired.  The timeout period elapsed prior to completion of the operation or the server is not responding. </p></div>'
    driver.find_element_by_class_name("alert.alert-error")
    """


def get_recipients_ids(driver):
    try:
        driver.find_element(
            by=By.CLASS_NAME,
            value="k-button.k-button-icontext.grid-row-button.k-grid-Use",
        ).click()

    # selenium.common.exceptions.NoSuchElementExceptions
    except:
        return False
    """
        If NoSuchElementExceptions - means there are no templates to pick from
    """
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

    soup = BeautifulSoup(driver.page_source, "html.parser")
    script_element = soup.find(text=re.compile("repeaterData"))
    raw_json = script_element[
        script_element.find("JSON.parse") : script_element.rfind("x7d'),")
    ]
    del soup
    raw_json_escapped = raw_json.encode().decode("unicode_escape", errors="ignore")
    repeater_json = json.loads(raw_json_escapped[12:] + "}")
    del raw_json_escapped

    with open("./repeater_script.json", "w") as f:
        f.write(json.dumps(repeater_json["Facilities"]))

    # json_script['TransferTypes']
    # To close the opened template pop-up
    # Instead of clicking on 'x'
    driver.refresh()
    return repeater_json["Facilities"]


def metrc_get_facilities(driver):
    repeater_json = ""
    if not Path("./repeater_script.json").is_file():
        facilities = get_recipients_ids(driver)
        if not facilities:
            return False

    with open("./repeater_script.json", "r") as f:
        repeater_json = f.read()
    repeater_json = json.loads(repeater_json)
    return repeater_json


def memory_dump():
    """
    List all the local variables in each stack frame.
    """
    tb = sys.exc_info()[2]
    while 1:
        if not tb.tb_next:
            break
        tb = tb.tb_next
    stack = []
    f = tb.tb_frame
    while f:
        stack.append(f)
        f = f.f_back
    # stack.reverse()

    dump = ""
    dump += traceback.format_exc() + "\n"

    dump += "Locals by frame:\n"
    fl_name = dt.datetime.now().strftime("%Y-%m-%d_%H_%M")
    for frame in stack[:]:
        dump += "Frame %s in %s at line %s" % (
            frame.f_code.co_name,
            frame.f_code.co_filename,
            frame.f_lineno,
        )
        for key, value in frame.f_locals.items():

            dump += "\t%20s = " % key
            # We have to be VERY careful not to cause a new error in our error
            # printer! Calling str(  ) on an unknown object could cause an
            # error we don't want, so we must use try/except to catch it --
            # we can't stop it from happening, but we can and should
            # stop it from propagating if it does happen!
            try:
                # print("DUMP:", sys.getsizeof(dump))
                # print("DUMP:", sys.getsizeof(value))
                dump += f"{value}\n"
            except:
                dump += "<ERROR WHILE GETTING VALUE>\n"
    with open(f"{paths['logs']}Dump_{fl_name}.txt", "w") as f:
        f.write(dump)


def send_slack_msg(msg):
    # For uploading an image:
    # https://stackoverflow.com/questions/66017386/cant-attach-uploaded-file-to-message-using-slack-api-via-python

    client = WebClient(token=slack_token)
    msg = "{}:\n{}".format(
        dt.datetime.strftime(
            dt.datetime.now(dt.datetime.now().astimezone().tzinfo),
            "%Y-%m-%dT%H:%M%z",
        ),
        msg,
    )
    response = client.chat_postMessage(channel="mail-test", text=msg)


def get_traceback(e):
    lines = traceback.format_exception(type(e), e, e.__traceback__)
    return "".join(lines) + "\n Please check the Logs dir for the screenshot."


def get_cookie_and_token(driver):

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
    return {"cookie": metrc_cookie, "token": metrc_api_verification_token}


def empty_prices_checker(driver):
    """Helper function to parse the price input fields from the metrc.
    If only one field is empty this fnc will return False, since
    having empty field will not let us register transfer.

    Args:
        source (str): webdriver html source

    Returns:
        bool: True or False
    """
    template_packages = len(
        driver.find_elements(By.XPATH, value="//*[@ng-model='package.WholesalePrice']")
    )
    # for i in range(template_packages):
    # el = soup.find(
    #     "input",
    #     {"name": f"model[0][Destinations][0][Packages][{i}][WholesalePrice]"},
    # )
    try:
        ## Try to find control-group ng-hide div. If its present that means that the price fields dont exist (element hidden = no prices)
        ss = driver.find_element(
            by=By.XPATH,
            value="//*[@name='model[0][Destinations][0][Packages][1][WholesalePrice]']/parent::div[@class='input-prepend']/parent::div[@class='controls']/parent::div[@class='control-group ng-hide']",
        )
        return False
    except:
        ## If element is not hidden, that means that the prices do exists (at this point they could still be empty)
        for i in range(template_packages):
            el = driver.find_element(
                By.NAME,
                value=f"model[0][Destinations][0][Packages][{i}][WholesalePrice]",
            ).get_attribute("value")
            if el.strip() == "":
                return True
    return False


def define_email_logger():
    import datetime as dt

    smtp_handler = logging.handlers.SMTPHandler(
        mailhost=("smtp.gmail.com", 587),
        fromaddr="finance@headquarters.co",
        toaddrs=[
            "stefanm2142@gmail.com",
            "katarina@headquarters.co",
            "marko@headquarters.co",
            "jovanaj@headquarters.co",
        ],
        credentials=("finance@headquarters.co", "Pluto7232"),
        subject=f"METRCxNABIS automation error! {dt.datetime.strftime(dt.datetime.today(), '%Y-%m-%d')}",
        secure=(),
        timeout=10.0,
    )
    email_logger = logging.getLogger("email_logger")
    email_logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(filename)s:%(lineno)s - %(funcName)s() %(message)s"
    )
    smtp_handler.setFormatter(formatter)
    email_logger.setLevel(logging.DEBUG)
    if len(email_logger.handlers) == 0:
        email_logger.addHandler(smtp_handler)
    return email_logger


def define_default_logger():
    logger = logging.getLogger("default_logger")
    logger.setLevel(logging.DEBUG)
    formatter_json = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(funcName)s %(message)s"
    )
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(filename)s:%(lineno)s - %(funcName)s() %(message)s"
    )
    file_handler = logging.handlers.RotatingFileHandler(
        paths["logs"] + r"METRCxNABIS.log", maxBytes=10485760, backupCount=5
    )
    # file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter_json)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(formatter)
    if len(logger.handlers) < 2:
        logger.addHandler(file_handler)
        logger.addHandler(consoleHandler)
    return logger


def duplicate_check(gc, order_id):
    """Check if a given order_id hasnt been done before.
        Check is being done in the offline copy of a log gsheet, to
        preserve the API quota.

    Args:
        gc (_type_): _description_
        order_id (int): order number as an int

    Returns:
        _type_: _description_
    """
    # sh = gc.open_by_url(
    #     urls['gsheet_logger']
    # )
    # try:
    #     wks = sh.worksheet("Logs")
    # except:
    #     time.sleep(61)
    #     wks = sh.worksheet("Logs")

    # sheet_df = pd.DataFrame(wks.get_all_records())
    # sheet_df["Order"].replace("", 0, inplace=True)
    # sheet_df["Order"] = pd.to_numeric(sheet_df["Order"], errors="coerce")

    off_log_df = pd.read_csv(f"{paths['logs']}Offline_log.csv")
    off_log_df["Order"].replace("", 0, inplace=True)
    off_log_df["Order"] = pd.to_numeric(off_log_df["Order"], errors="coerce")
    off_log_df["Order"].astype("Int64")

    if int(order_id) in off_log_df[off_log_df["ALL_GOOD"] == True]["Order"].tolist():
        # It is duplicate
        return True
    else:
        # Its not a duplicate
        return False


def thread_fnc(gc):
    # https://stackoverflow.com/questions/48745240/python-logging-in-multi-threads
    try:
        sh = gc.open_by_url(urls["gsheet_logger"])
    except:
        time.sleep(110)
        sh = gc.open_by_url(urls["gsheet_logger"])

    wks = sh.worksheet("API_Log(wip)")
    sheet_df = pd.DataFrame(wks.get_all_records())
    start_time = time.time()
    rows_count = sheet_df.shape[0]
    while True:
        if (time.time() - start_time) > 600:
            start_time = time.time()
            sheet_df = pd.DataFrame(wks.get_all_records())
            if rows_count == sheet_df.shape[0]:
                send_slack_msg(
                    "<@U0114CKP5UP> Same number of orders for the last 10 minutes"
                )
            else:
                rows_count = sheet_df.shape[0]
        else:
            time.sleep(60)
            print(f"Thread 60 seconds idle tick..{time.time() - start_time}")


def update_log_sheet(log_dict, gc):
    # Update logging gsheet file

    @retry(wait=wait_fixed(5))
    def helper_get_gsheet_data():
        sh = gc.open_by_url(urls["gsheet_logger"])
        wks = sh.worksheet("API_Log(wip)")
        return wks

    wks = helper_get_gsheet_data()
    sheet_df = pd.DataFrame(wks.get_all_records())

    df_dict = pd.DataFrame([log_dict])
    output = pd.concat([sheet_df, df_dict], ignore_index=True)
    output.fillna("", inplace=True)
    try:
        output["WrongPrice"] = output["WrongPrice"].apply(str)
        output["WrongQuantity"] = output["WrongQuantity"].apply(str)
        output["MissingPackageTag"] = output["MissingPackageTag"].apply(str)
    except:
        pass

    wks.update([output.columns.values.tolist()] + output.values.tolist())

    output.to_csv(f"{paths['logs']}Offline_log.csv", index=False)


def finish_template_get_manifest(
    driver, WAREHOUSE, nabis_order, transport_detail_flags, logger
):

    ### SUBMIT BUTTON
    fl_name = str(dt.datetime.today()).replace(":", ".")
    ob = Screenshot_Clipping.Screenshot()
    img_url = ob.full_Screenshot(
        driver,
        save_path=r".",
        image_name=f"{paths['template_sc']}Template_{fl_name}.jpg",
    )

    # try:
    #     driver.save_screenshot(f"{paths['template_sc']}Template_{fl_name}.jpg")
    # except UnboundLocalError:
    #     pass

    logger.info(f"[{nabis_order['id']}] Registering transfer...")
    driver.find_element(
        by=By.XPATH, value='//*[@id="addedit-transfer_form"]/div/button[1]'
    ).click()

    # Waiting for the Transfer pop-up to close itself
    bool = True
    while bool:
        try:
            time.sleep(0.5)

            driver.find_element(
                by=By.XPATH, value='//*[@id="addedit-transfer_form"]/div/button[1]'
            )
        except:
            bool = False
            pass
    logger.info(f"[{nabis_order['id']}] Transfer registration completed.")
    ### AFTER SUBMITTING A TEMPLATE
    # For licensed transfer (not the same as templates for transfer), this is 2nd step
    # Remove Template
    logger.info("Voding transfer template...")
    driver.find_element(by=By.XPATH, value="//*[@title='Discontinue']").click()
    alert_obj = driver.switch_to.alert
    alert_obj.accept()
    time.sleep(1)
    logger.info(f"[{nabis_order['id']}] Voiding completed.")

    logger.info("Opening outgoing transfers")
    try:
        driver.get(f"https://ca.metrc.com/industry/{WAREHOUSE}/transfers/licensed")
    except:
        time.sleep(5)
        driver.get(f"https://ca.metrc.com/industry/{WAREHOUSE}/transfers/licensed")

    driver.find_element_by_id("outgoing-tab").click()
    time.sleep(0.5)

    # WebDriverWait(driver, 15).until(
    #     EC.invisibility_of_element_located(
    #         (By.CLASS_NAME, "tab-select-one text-center")
    #     )
    # )

    bool = True
    while bool:
        try:
            time.sleep(0.5)

            driver.find_element(By.CLASS_NAME, value="k-loading-image")
        except:
            bool = False
            pass
    # WebDriverWait(driver, 20).until(
    #     EC.visibility_of_element_located((By.CLASS_NAME, "k-loading-image"))
    # )
    # EC.element

    logger.info(f"[{nabis_order['id']}] Outgoing transfers loaded. Getting row data")
    rows = driver.find_elements(
        by=By.CLASS_NAME, value="k-master-row.grid-editable-row"
    )
    if not rows:
        pass
    current_files = len(get_cwd_files())
    manifest_id = None
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
        logger.info(
            f"[{nabis_order['id']}] ManifestID found: {manifest_id}, date created: {manifest_date_created}, {employee}"
        )

        if employee == "Aleksandar Plavljanic":
            logger.info("Downlaoding manifest pdf...")
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

            logger.info(f"[{nabis_order['id']}] File downloaded {list_of_pdf[0]}")

            # o = get_order_data(nabis_order["orderNumber"])
            transfer = view_metrc_transfer(nabis_order["id"])
            transfer_id = [
                x["id"]
                for x in transfer["data"]["getMetrcTransfers"]
                if nabis_order["shipment_template"] == x["metrcTransferTemplateName"]
            ][0]
            logger.info(f"[{nabis_order['id']}] list_of_pdfs: {list_of_pdf}")
            logger.info(f"[{nabis_order['id']}] File to be uploaded {list_of_pdf[0]}")

            order_notes = ""
            for k, v in transport_detail_flags.items():
                if v == "FLAG":
                    order_notes += f"TEMP {k};"
            if order_notes != "":
                logger.info(
                    f"[{nabis_order['id']}] Uploading order notes: {order_notes}"
                )
                order_response = upload_order_note(transfer_id, order_notes)
            else:
                logger.info("No order notes")

            pdf_response = upload_manifest_pdf(
                transfer_id, paths["pdfs"] + list_of_pdf[0]
            )
            id_response = upload_manifest_id(transfer_id, manifest_id)
            if (pdf_response == "errors") or (pdf_response == False):
                logger.error(
                    f'Error while uploading manifest pdf {transfer_id}, order: {nabis_order["id"]}'
                )
            if ("errors" in id_response) or (id_response == False):
                logger.error(
                    f'Error while uploading manifest id number {transfer_id}, order {nabis_order["id"]}'
                )

            return {
                "manifest_id": manifest_id,
                "pdf_response": pdf_response,
                "id_response": id_response,
                "order_note": order_notes,
            }

    return False


def get_spreadsheet_routes(gc):

    sh = gc.open_by_url(urls["gsheet_routes"])

    known_sheets = ["LA routes", "OAK routes", "4Front routes"]
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
        "download.default_directory": f"{os.getcwd()}{paths['selenium_download_dir']}",
        "download.prompt_for_download": False,
        "profile.default_content_setting_values.geolocation": 2,
    }

    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--window-size=1536,865")

    driver = webdriver.Chrome(
        executable_path=paths["chromedriver"], chrome_options=chrome_options
    )
    return driver


def get_cwd_files():
    list_of_files = filter(
        lambda x: os.path.isfile(os.path.join(paths["pdfs"], x)),
        os.listdir(paths["pdfs"]),
    )
    try:
        list_of_files = sorted(
            list_of_files,
            key=lambda x: os.path.getmtime(os.path.join(paths["pdfs"], x)),
        )
    except FileNotFoundError:
        time.sleep(2)
        list_of_files = filter(
            lambda x: os.path.isfile(os.path.join(paths["pdfs"], x)),
            os.listdir(paths["pdfs"]),
        )
        list_of_files = sorted(
            list_of_files,
            key=lambda x: os.path.getmtime(os.path.join(paths["pdfs"], x)),
        )

    list_of_files = list([x for x in list_of_files if ".pdf.crdownload" not in x])
    list_of_files = list([x for x in list_of_files if ".pdf" in x])
    list_of_files = list([x for x in list_of_files if ".tmp" not in x])
    list_of_files.reverse()  # 0th element is the newest
    return list_of_files
