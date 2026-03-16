"""
Test Cloudbeds API connection for all properties.
Run: python test_cloudbeds.py
"""
import urllib.request
import json

PROPERTIES = [
    ("HiD Taipei",  "25496",  "cbat_UnJezJUNCKPnyre1YeewOvKGLHIAABhN"),
    ("HiD Saigon",  "185944", "cbat_CLbBoz9KsiMF8VuHexwhe2FoTXnOyvmf"),
    ("HiD 1948",    "22872",  "cbat_z1yUm28bgKSZRVnisFo5SwigZi5wK2Rn"),
    ("HiD Oani",    "318301", "cbat_fMUrxDEPvb0setdICb9GfMzNHKpWXU0F"),
    ("HiD Osaka",   "301582", "cbat_opm3MzseiOu2VlGpxKOogDNca0IHIhUy"),
]

BASE = "https://hotels.cloudbeds.com/api/v1.2"

for name, prop_id, api_key in PROPERTIES:
    url = f"{BASE}/getProperty?propertyID={prop_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("success"):
                p = data.get("data", {})
                print(f"OK  {name}: {p.get('propertyName','?')} | rooms={p.get('roomCount','?')}")
            else:
                print(f"FAIL {name}: {data.get('message','unknown error')}")
    except Exception as e:
        print(f"ERR  {name}: {e}")
