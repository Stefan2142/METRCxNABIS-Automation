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
from creds import slack_token
from config import paths, urls
import traceback
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from tenacity import retry, wait_fixed


def waiting_fnc(driver, path):
    """[NOT IMPLEMENTED YED] Fnc utilizing while loop which gives a correctly waiting function
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
    with open(f"{paths['logs']}Dump_{fl_name}.txt", "w", encoding="utf8") as f:
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


@retry(wait=wait_fixed(5))
def get_cookie_and_token(driver, WAREHOUSE, credentials):

    cookie_list = driver.get_cookies()
    soup = BeautifulSoup(driver.page_source, "html.parser")
    try:
        metrc_api_verification_token = (
            str(soup(text=re.compile(r"ApiVerificationToken")))
            .split("X-Metrc-LicenseNumber")[0]
            .split("ApiVerificationToken")[-1]
            .split("'")[2]
        )
    except:
        driver = metrc_driver_login(driver, WAREHOUSE, credentials)
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


def define_email_logger():
    import datetime as dt

    smtp_handler = logging.handlers.SMTPHandler(
        mailhost=("smtp.gmail.com", 587),
        fromaddr="finance@headquarters.co",
        toaddrs=[
            "stefan@headquarters.co",
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


def duplicate_check(order_id, shipment_id):
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
        if (
            int(shipment_id)
            in off_log_df[off_log_df["ALL_GOOD"] == True]["Shipment"].tolist()
        ):
            # It is duplicate
            return True
        else:
            return False
    else:
        # Its not a duplicate
        return False


def slack_idle_notif_thr(gc):
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
        "profile.default_content_setting_values.automatic_downloads": 1,
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


def metrc_driver_login(driver, WAREHOUSE, credentials):
    driver.get(f"https://ca.metrc.com/log-in")

    # Input username
    try:
        driver.find_element(by=By.XPATH, value='//*[@id="username"]').send_keys(
            credentials["metrc"]["un"]
        )
    except:

        return False
    # Input password
    driver.find_element(by=By.XPATH, value='//*[@id="password"]').send_keys(
        credentials["metrc"]["pwd"]
    )
    # Click login
    driver.find_element(by=By.XPATH, value='//*[@id="login_button"]').click()
    driver.get(
        f"https://ca.metrc.com/industry/{WAREHOUSE['license']}/transfers/licensed/templates"
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
