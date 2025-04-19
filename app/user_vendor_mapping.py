import json
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

MAPPING_FILE = os.path.join(BASE_DIR, "data", "user_vendor_mapping.json")
VENDORS_CONFIG_DIR = os.path.join(BASE_DIR, "data", "vendors.json")

def save_user_vendor_mapping(user_id: int, vendor_id: str):
    if not os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            mapping = json.load(f)
    else:
        mapping = {}

    mapping[str(user_id)] = vendor_id
    try:
        with open(MAPPING_FILE, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving mapping: {e}")

def get_vendor_id_for_user(user_id: int) -> str | None:
    if not os.path.exists(MAPPING_FILE):
        return None

    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    return mapping.get(str(user_id))


def load_vendor_config(vendor_name: str) -> dict:
    VENDORS_CONFIG_DIR
    if not os.path.exists(VENDORS_CONFIG_DIR):
        return None

    with open(VENDORS_CONFIG_DIR, "r", encoding="utf-8") as f:
        vendors_json = json.load(f)

    vendors = vendors_json.get("vendors", [])
    for vendor in vendors:
        if vendor.get("name") == vendor_name:
            selcted_vendor = vendor
            break
    else:
        return None
    return selcted_vendor