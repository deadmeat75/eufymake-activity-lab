"""Parse Studio imports without storing the complete profile files."""
import json
import ssl
import urllib.parse
from .protocol import BROKERS


def parse_imports(device_bytes, login_bytes, certificate_bytes):
    if max(len(device_bytes), len(login_bytes), len(certificate_bytes)) > 2 * 1024 * 1024:
        raise ValueError("File too large")
    try:
        devices = json.loads(device_bytes)["data"]
        user = json.loads(login_bytes)["data"]
        ca = certificate_bytes.decode("ascii")
        if "PRIVATE KEY" in ca:
            raise ValueError("Not a CA certificate")
        ssl.create_default_context(cadata=ca)
        uid = str(user["user_id"])
        email = urllib.parse.unquote(user["email"])
        region = str(user.get("ab_code") or "US").upper()
        if region not in BROKERS or not uid or not email:
            raise ValueError("Unsupported region or missing account information")
        if not isinstance(devices, list) or not devices:
            raise ValueError("No printers")
        choices = []
        for device in devices:
            serial, key = device["station_sn"], device["secret_key"]
            if not isinstance(serial, str) or not serial.strip() or not isinstance(key, str) or len(key) != 64 or len(bytes.fromhex(key)) != 32:
                raise ValueError("Invalid printer credentials")
            choices.append({"user_id": uid, "email": email, "region": region,
                "serial": serial, "secret_key": key, "ca_pem": ca})
        return choices
    except (KeyError, TypeError, ValueError, UnicodeError, ssl.SSLError) as error:
        raise ValueError("Invalid Studio files") from None
