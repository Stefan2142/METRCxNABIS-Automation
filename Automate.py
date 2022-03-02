import requests
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
import os
from bs4 import BeautifulSoup
import pandas as pd
import time


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


def main():
    driver = get_driver()
    driver.get("https://app.getnabis.com/sign-in")

    driver.find_element_by_xpath(
        '//*[@id="sign-in"]/div[1]/div/div[1]/input'
    ).send_keys("marko@nabis.com")

    driver.find_element_by_xpath(
        '//*[@id="sign-in"]/div[2]/div/div[1]/input'
    ).send_keys("Nabis123!")

    driver.find_element_by_xpath('//*[@id="sign-in"]/button[2]').click()
    driver.find_element_by_class_name("ui button").click()

    # Get on Admin Shipments Tracker Page
    driver.get(
        "https://app.getnabis.com/nabione-inc-deliveries/app/admin-shipment-tracker"
    )
    print("what now?")

    """driver.get("https://ca.metrc.com/")

    driver.find_element_by_xpath('//*[@id="username"]').send_keys(
        "alex@headquarters.co"
    )
    driver.find_element_by_xpath('//*[@id="password"]').send_keys("s9tjpBYiNfCJ*9m")
    driver.find_element_by_xpath('//*[@id="login_button"]').click()

    wait = WebDriverWait(driver, 15)

    time.sleep(0.3)
    # wait.until(
    #         EC.visibility_of_element_located(
    #             (By.CLASS_NAME, 'icon-box__wrapper')
    #         )
    #     )
    soup = BeautifulSoup(driver.page_source, "html.parser")"""


if __name__ == "__main__":
    main()
