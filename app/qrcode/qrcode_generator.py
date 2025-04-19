import qrcode
import os
import json

BASE_DIR = BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
VENDORS_CONFIG_DIR = os.path.join(BASE_DIR, "data", "vendors.json")

def open_vendors_config() -> dict:
    if os.path.exists(VENDORS_CONFIG_DIR):
        with open(VENDORS_CONFIG_DIR, "r", encoding="utf-8") as f:
            vendors_json = json.load(f)
    else:
        vendors_json = {}
    return vendors_json

def create_qr()-> None:

    for vendor in open_vendors_config().get("vendors", []):
        vendor_id = vendor.get("vendor_id")
        vendor_name = vendor.get("name")
        vendor_link = vendor.get("deep_link")
        if vendor_id and vendor_name and vendor_link:
            filename = os.path.join(BASE_DIR, "data", f"{vendor_id}_{vendor_name}.png")
            img = qrcode.make(vendor_link)
            img.save(filename)
            print(f"✅ QR code saved to {filename}")

if __name__ == "__main__":
    create_qr()