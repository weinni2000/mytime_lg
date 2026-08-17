# pylint: disable=print-used
import json

import requests

url = "https://camping.unternhub.at/booking/key"

payload = json.dumps({"key": "xyz", "message": "abc"})
headers = {
    "Content-Type": "application/json",
    "Cookie": "session_id=rXLEMEUAOGqXz_6Ajpk9x-IXMshqHX32SpSi2y7brOMzo4f1F-D8E-veEOUVNyipFHa0vogXDBPqfBOsNDYK",
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
