import requests
import json

url = "https://ca.metrc.com/api/transfers/create"

payload = json.dumps(
    [
        {
            "ShipmentLicenseType": "Licensed",
            "Destinations": [
                {
                    "ShipmentLicenseType": "Licensed",
                    "RecipientId": "33101",
                    "PlannedRoute": "NABIS 159986 Los Angeles to Vista via I-5 S on a multi stop route.",
                    "TransferTypeId": "111",
                    "EstimatedDepartureDateTime": "2022-04-28T07:00:00",
                    "EstimatedArrivalDateTime": "2022-04-28T17:00:00",
                    "GrossWeight": "",
                    "GrossUnitOfWeightId": "",
                    "Transporters": [
                        {
                            "TransporterId": "142201",
                            "PhoneNumberForQuestions": "(628) 219-4330",
                            "EstimatedArrivalDateTime": "2022-04-28T17:00:00",
                            "EstimatedDepartureDateTime": "2022-04-28T07:00:00",
                            "TransporterDetails": [
                                {
                                    "DriverName": "Anthony Maccarello",
                                    "DriverOccupationalLicenseNumber": "736877464",
                                    "DriverLicenseNumber": "736877464",
                                    "VehicleMake": "Mercedes Benz",
                                    "VehicleModel": "S48 Sprinter Cargo Van",
                                    "VehicleLicensePlateNumber": "CA80J54",
                                }
                            ],
                        }
                    ],
                    "Packages": [
                        {
                            "Id": "24618655",
                            "WholesalePrice": "0.11",
                            "GrossWeight": "",
                            "GrossUnitOfWeightId": "",
                        }
                    ],
                }
            ],
        }
    ]
)

headers = {
    "authority": "ca.metrc.com",
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "en-US,en;q=0.9",
    # apiVerificationToken
    "apiverificationtoken": "QkrWqVKO5JcvPJED4zD_XQJgPlkmK6h1SMUE2f_Z5kEqEwkhTyREGK758tHJiAwAueWZH14lAU26fuoQV_4qu7ZQquLvkeQi9z4N9UkFE2Pah5c5uTkg30ekn9XyD9rrRsHpbxOYKsiIqgt7XmUMyw2:18I_VGy2GDrmoXpkmv-wr7nI3_aEiRQYPWwLjuLKleuNSNvOcTURxVycNb6QIPsBNO1K1woethBCqF52hqj2dwd31Atd2rGeRr3vC3e3b3v4IdtC_LXYtyuACN8qKt1YUfG1wSbGFIZK9URSeMFPusZrkQk4ttteWH0A1fzsINk1",
    "content-type": "application/json",
    "cookie": "MetrcRequestToken=Z37OzvsElNWVo2zdEEmvYKsEwIW7WO2F1eGEnnGcbasoodkvONWMuQJMgvsi5N1vB2RkMBm71jB2GtSlf4T-eF8MtaSU3lYyLOUebwQ-7Vdcd2t__3U0oXu8ndSkvp5PQHjul6P5Z7-jbhC-l_b8nQ2; MetrcAuth=125E02107E7FEE768939D784CA894AF938762F5F1C681E1115645F268C97E17574AF43CC9A6281A8C5235DA52FA945C9557CDDB426EBAD58CC0BF32388D593B8074F9A87965932BFC081252BFF5C4ADCEC9F97E92A6967059C61B758282BEF271C3BE40EEBF12E12528430BAAA143D269B8476FD66944B4D40FC3A0634DA8056701880094B085278E65F923BF8A70CA66B9E54D8A9D9E62CC636EE95406F7C6C7FBAAFAAC14E4802C0F44F95EF1EC604073D53B9895C7097B834B791E4FE95D69BFF3F0BE7167C1522BB1193450A95C31103B1264F90C1E46EFFCC5BF0A5AA92373E0926EFE8F7E2954897653DD23D376835AC0C3765CDA3A643D3F7028E850CC68E2FBECAF4B2835C3A65C9706C6D64EA3B4AA49D0927B7665AFFE4586BDEDBD2160E9160C46DE1D1753E5980901AC3AF6A996B23837A8725A5A06C80D90DB7; MetrcSessionTime=2022-04-27T21:33:35Z; MetrcAuth=2E4ADEB6B5211E3B287813BFCD56766AD2A2D1902B66FA4442C9C6B351C706033968135D4F3A48C37D90E046CB9EBB6FD91DD6EB44D601350B1AD7D5A3850499A7C33286A7FB0D9917C8211979FCC18C3155CD84FAE352D7162D4D095FE0C07AAD87F1A0604260188C21B46743EE7DE25E422BAD4CD075A8962360FFA741A87EAA41467E2F9907312A8DAB93D720CB8F3A2A192FEB2603F76527EB8D7018FC9093C4881715CB481B86C4DF95340353AF881C18BF97F53408041E695E0762D5F65C20B208146AC5D4225952BF1E465B73D0B6339CCF767DDD1CE30EA817656BDE6469003180C279348D802F20B020DC972D07103ADF0698F9C75936F3617FF756697D20FEEB26E81DC83168F45B2205961EE7FAE99907E9C0557327CE7F5ED3DA69179707D7B06FD2541FC2442C416B2000D7DAE52D99B05CCC7D22C355922BEA; MetrcSessionTime=2022-04-27T21:48:43Z",
    "newrelic": "eyJ2IjpbMCwxXSwiZCI6eyJ0eSI6IkJyb3dzZXIiLCJhYyI6IjI2NTk5OTUiLCJhcCI6IjMxOTYwNDkzNyIsImlkIjoiNWYzNTMyMGM3YzMxNzgyZCIsInRyIjoiZDYxZjAxMTBkMWY4ZWUwYTRhMzk3YjIyOTIyMzlmYTAiLCJ0aSI6MTY1MTA5MzY0NDA3NX19",
    "origin": "https://ca.metrc.com",
    "referer": "https://ca.metrc.com/industry/C11-0000340-LIC/transfers/licensed/templates",
    "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "traceparent": "00-d61f0110d1f8ee0a4a397b2292239fa0-5f35320c7c31782d-01",
    "tracestate": "2659995@nr=0-1-2659995-319604937-5f35320c7c31782d----1651093644075",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
    # This one
    "x-metrc-licensenumber": "C11-0000340-LIC",
    # This one
    "x-newrelic-id": "VgACWF9aDRADVVhRDgUHXlU=",
    "x-requested-with": "XMLHttpRequest",
}


headers = {
    "ApiVerificationToken": "QkrWqVKO5JcvPJED4zD_XQJgPlkmK6h1SMUE2f_Z5kEqEwkhTyREGK758tHJiAwAueWZH14lAU26fuoQV_4qu7ZQquLvkeQi9z4N9UkFE2Pah5c5uTkg30ekn9XyD9rrRsHpbxOYKsiIqgt7XmUMyw2:18I_VGy2GDrmoXpkmv-wr7nI3_aEiRQYPWwLjuLKleuNSNvOcTURxVycNb6QIPsBNO1K1woethBCqF52hqj2dwd31Atd2rGeRr3vC3e3b3v4IdtC_LXYtyuACN8qKt1YUfG1wSbGFIZK9URSeMFPusZrkQk4ttteWH0A1fzsINk1",
    "X-Metrc-LicenseNumber": "C11-0000340-LIC",
    "sec-ch-ua-mobile": "?0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://ca.metrc.com",
    "Cookie": "MetrcRequestToken=Z37OzvsElNWVo2zdEEmvYKsEwIW7WO2F1eGEnnGcbasoodkvONWMuQJMgvsi5N1vB2RkMBm71jB2GtSlf4T-eF8MtaSU3lYyLOUebwQ-7Vdcd2t__3U0oXu8ndSkvp5PQHjul6P5Z7-jbhC-l_b8nQ2; MetrcAuth=125E02107E7FEE768939D784CA894AF938762F5F1C681E1115645F268C97E17574AF43CC9A6281A8C5235DA52FA945C9557CDDB426EBAD58CC0BF32388D593B8074F9A87965932BFC081252BFF5C4ADCEC9F97E92A6967059C61B758282BEF271C3BE40EEBF12E12528430BAAA143D269B8476FD66944B4D40FC3A0634DA8056701880094B085278E65F923BF8A70CA66B9E54D8A9D9E62CC636EE95406F7C6C7FBAAFAAC14E4802C0F44F95EF1EC604073D53B9895C7097B834B791E4FE95D69BFF3F0BE7167C1522BB1193450A95C31103B1264F90C1E46EFFCC5BF0A5AA92373E0926EFE8F7E2954897653DD23D376835AC0C3765CDA3A643D3F7028E850CC68E2FBECAF4B2835C3A65C9706C6D64EA3B4AA49D0927B7665AFFE4586BDEDBD2160E9160C46DE1D1753E5980901AC3AF6A996B23837A8725A5A06C80D90DB7;",
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
