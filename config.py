from creds import nabis_bearer_token

SMALL_WAIT = 5
LARGE_WAIT = 10
# pronadji gsheet-ove, direktorijume itd i dodaj ih u config
# gitignore - izbaciti nepotrebne foldere i fajlove
# promeniti za PDF downloads folder
# Mozda glavni fajl srediti kod
# na kraju, mozda logiku srediti


paths = {
    "selenium_download_dir": "\\PDFs\\",
    "pdfs": "./PDFs/",
    "logs": "./Logs/",
    "errors_sc": "./Logs/Screenshots/",
    "template_sc": "./PDFs/TemplateScs/",
    "chromedriver": "./chromedriver.exe",
}

urls = {
    "gsheet_logger": "https://docs.google.com/spreadsheets/d/1LkP08iIUIZyRz-_C45AJ0FvRJuwGK_SzuZylfNMrAuE",
    "gsheet_routes": "https://docs.google.com/spreadsheets/d/1gGctslxmXIO490qnKPN2SbWZV2ZLT7Z3zIpxQo19us8",
}
###############
GARDEN_OF_WEEDEN = {
    "name": "Garden of Weeden",
    "license": "C11-0000340-LIC",
    "id": "QWxsTGljZW5zZWRMb2NhdGlvblNpbXBsaWZpZWQ6NDFkYjA5NDctZDFmMy00OTU1LWFmMjAtZDg5MmYxODYwMTA5",
}
NABITWO = {
    "name": "Nabitwo",
    "license": "C11-0001274-LIC",
    "id": "QWxsTGljZW5zZWRMb2NhdGlvblNpbXBsaWZpZWQ6MGNlZGNmNmQtODc4NC00Yjc2LWJlOWMtMGUxMDJlNTI0NWY5",
}

front_commerce = {
    "name": "4Front",
    "license": "C11-0000825-LIC",
    "id": "QWxsTGljZW5zZWRMb2NhdGlvblNpbXBsaWZpZWQ6YzQ4YTZkYmEtOTU2Yy00MDFhLTg0MGUtYTk4OWQ1YWI1MWM3",
}

# Here pick the desired warehouse
WAREHOUSE = GARDEN_OF_WEEDEN


"""C11-0001274-LIC - Nabitwo
        C11-0000340-LIC - Garden of Weeden
        C11-0000825-LIC - Cannex / 4Front"""

nabis_warehouse_licenses = [
    "C11-0001274-LIC",
    "C11-0000340-LIC",
    "C11-0000825-LIC",
]

# --- Nabis api---#
nabis_api_url = "https://api.getnabis.com/graphql/admin"

nabis_headers = {
    "authority": "api.getnabis.com",
    "accept": "*/*",
    "authorization": nabis_bearer_token,
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
    "content-type": "application/json",
}


matching_attrs = {
    "license": {
        "metrc": {"key": "metrc_destination_license", "data": None},
        "nabis": {"key": "nabis_destination_license", "data": None},
        "metrc_key": '//*[@ng-model="destination.RecipientId"]',
        "nabis_key": "siteLicenseNum",
        "error_incorrect_key": "IncorrectLicense",
        "error_incorrect_msg": "Licenses doesnt match metrc: {} vs nabis: {}",
    },
    "route": {
        "metrc_key": "model[0][Destinations][0][PlannedRoute]",
        "metrc": {"key": "metrc_planned_route", "data": None},
    },
    "est_departure_date": {"metrc": {"key": "metrc_est_departure", "data": None}},
    "est_arrival_date": {
        "metrc": {"key": "metrc_est_arrival", "data": None},
    },
    "driver": {
        "metrc": {"key": "metrc_driver", "data": None},
        "nabis": {"key": "nabis_driver", "data": None},
        "metrc_key": '//*[@ng-model="transporterDetail.DriverName"]',
        "nabis_key": "",
        "error_incorrect_key": "IncorrectDriver",
        "error_missing_key": "MissingDriver",
        "error_incorrect_msg": "Driver name incorrect; Metrc: {} vs nabis: {}",
        "error_missing_msg": "Driver name missing; Metrc: {} vs nabis: {}",
    },
    "driver_id": {
        "metrc": {"key": "metrc_driver_id", "data": None},
        "nabis": {"key": "nabis_driver_id", "data": None},
        "metrc_key": '//*[@ng-model="transporterDetail.DriverOccupationalLicenseNumber"]',
        "nabis_key": "",
        "error_incorrect_key": "IncorrectDriverId",
        "error_missing_key": "MissingDriverIdNabis",
        "error_incorrect_msg": "Driver ID incorrect; Metrc: {} vs nabis: {}",
        "error_missing_msg": "Driver ID missing; Metrc: {} vs nabis: {}",
    },
    "vehicle_make": {
        "metrc": {"key": "metrc_vehicle_make", "data": None},
        "nabis": {"key": "nabis_vehicle_make", "data": None},
        "metrc_key": '//*[@ng-model="transporterDetail.VehicleMake"]',
        "nabis_key": "",
        "error_incorrect_key": "IncorrectVehicleMake",
        "error_missing_key": "MissingVehicleMakeNabis",
        "error_incorrect_msg": "Vehicle maker incorrect; Metrc: {} vs nabis: {}",
        "error_missing_msg": "Vehicle maker missing; Metrc: {} vs nabis: {}",
    },
    "vehicle_model": {
        "metrc": {"key": "metrc_vehicle_model", "data": None},
        "nabis": {"key": "nabis_vehicle_model", "data": None},
        "metrc_key": '//*[@ng-model="transporterDetail.VehicleModel"]',
        "nabis_key": "",
        "error_incorrect_key": "IncorrectVehicleModel",
        "error_missing_key": "MissingVehicleModelNabis",
        "error_incorrect_msg": "Vehicle model incorrect; Metrc: {} vs nabis: {}",
        "error_missing_msg": "Vehicle model missing; Metrc: {} vs nabis: {}",
    },
    "vehicle_plate": {
        "metrc": {"key": "metrc_license_plate", "data": None},
        "nabis": {"key": "nabis_license_plate", "data": None},
        "metrc_key": '//*[@ng-model="transporterDetail.VehicleLicensePlateNumber"]',
        "nabis_key": "",
        "error_incorrect_key": "IncorrectVehiclePlate",
        "error_missing_key": "MissingVehiclePlateNabis",
        "error_incorrect_msg": "Vehicle plate incorrect; Metrc: {} vs nabis: {}",
        "error_missing_msg": "Vehicle plate missing; Metrc: {} vs nabis: {}",
    },
}
