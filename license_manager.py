"""
AURA TACTICAL VISION // COMMERCIAL LICENSE & HWID AUTHENTICATION ENGINE
Supports:
1. Hardware-ID (HWID) extraction via Windows MachineGuid
2. Cryptographic signature check (HMAC-SHA256)
3. Online Cloud Verification (HTTP/JSON endpoint or GitHub/Pastebin Raw)
4. HWID-Locking (Prevents key sharing across multiple PCs)
5. Expiration & Subscription tier validation (Day, Month, Lifetime)
"""

import sys
import os
import json
import time
import winreg
import hmac
import hashlib
import urllib.request
import urllib.error

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_AUTH_CACHE = os.path.join(BASE_DIR, "loader_auth.json")

# Master secret key for cryptographic offline signature verification (Change this for your brand)
SECRET_SALT = b"AURA_TACTICAL_CYBER_SUITE_2026_SUPER_SECRET"

# Optional Cloud API / GitHub Raw / Web Server URL for online key validation & HWID binding
# Set your URL here (e.g. GitHub raw, Pastebin, or your VPS endpoint)
# Format expected from server:
# {
#    "KEYS": {
#        "AURA-PRO-XXXX-XXXX": {"hwid": "XXXX-XXXX", "tier": "Lifetime", "expires": "2028-01-01", "status": "active"}
#    }
# }
CLOUD_AUTH_URL = ""


def get_machine_hwid() -> str:
    """Retrieve permanent Windows MachineGuid and format as standard commercial HWID."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        )
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        h = hashlib.sha256(guid.encode("utf-8")).hexdigest()[:16].upper()
        return "-".join([h[i:i+4] for i in range(0, 16, 4)])
    except Exception:
        return "HWID-8842-10F9-C43A"


def generate_cryptographic_key(tier="LIFETIME", duration_days=365) -> str:
    """
    Generates a cryptographically signed commercial license key:
    Format: AURA-[TIER]-[RANDOM]-[SIGNATURE]
    """
    import random
    rand_chunk = f"{random.randint(1000, 9999)}"
    tier_up = tier.upper()
    if "5D" in tier_up or "DAY" in tier_up:
        tier_tag = "5DAY"
    elif "LIFE" in tier_up:
        tier_tag = "LIFE"
    else:
        tier_tag = "SUB"
    payload = f"{tier_tag}-{rand_chunk}"
    sig = hmac.new(SECRET_SALT, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:8].upper()
    sig_formatted = f"{sig[:4]}-{sig[4:]}"
    return f"AURA-{payload}-{sig_formatted}"


def verify_cryptographic_signature(key_str: str) -> bool:
    """Verifies if key was signed with the admin secret salt."""
    key_clean = key_str.strip().upper()
    parts = key_clean.split("-")
    if len(parts) == 5 and parts[0] == "AURA":
        payload = f"{parts[1]}-{parts[2]}"
        sig_in = f"{parts[3]}{parts[4]}"
        expected_sig = hmac.new(SECRET_SALT, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:8].upper()
        return sig_in == expected_sig
    return False


class LicenseManager:
    def __init__(self):
        self.hwid = get_machine_hwid()
        self.cached_auth = self._load_cache()

    def _load_cache(self) -> dict:
        if os.path.exists(LOCAL_AUTH_CACHE):
            try:
                with open(LOCAL_AUTH_CACHE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_cache(self, key: str, tier: str, bound_hwid: str, remember: bool, days=None):
        expires_at = (time.time() + (days * 86400)) if days else None
        data = {
            "license_key": key,
            "tier": tier,
            "hwid": bound_hwid,
            "activated": True,
            "remember": remember,
            "activated_at": time.time(),
            "expires_at": expires_at,
            "last_verified": time.time()
        }
        try:
            with open(LOCAL_AUTH_CACHE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass
        self.cached_auth = data

    def validate_key(self, key_str: str, remember=True) -> tuple[bool, str, str]:
        """
        Validates license key against:
        1. Cloud Auth Server (if configured)
        2. Local Database / Cryptographic Signed Token
        3. HWID Binding Check

        Returns: (success: bool, tier_or_error_msg: str, plan_name: str)
        """
        key = key_str.strip().upper()
        if not key:
            return False, "License key cannot be empty.", ""

        # A. Check Master / VIP Admin Keys (Built-in keys for instant testing & sales)
        master_keys = {
            "AURA-VIP-2026-LIFETIME": ("LIFETIME PRO", "All Games & Engines", None),
            "AURA-5DAY-VIP-ACCESS": ("5-DAY VIP TRIAL", "5-Day Uncapped Access", 5),
            "AURA-PRO-FOUNDER-PASS": ("FOUNDER EDITION", "Full Access Uncapped", None),
            "AURA-DEV-MASTER-ACCESS": ("DEVELOPER ACCESS", "Zero-Latency Debug", None),
        }

        if key in master_keys:
            tier, desc, days = master_keys[key]
            self.save_cache(key, tier, self.hwid, remember, days=days)
            return True, f"Activated: {tier}", desc

        # B. Online Cloud Validation (if CLOUD_AUTH_URL is defined)
        if CLOUD_AUTH_URL and CLOUD_AUTH_URL.startswith("http"):
            try:
                req = urllib.request.Request(
                    CLOUD_AUTH_URL,
                    headers={"User-Agent": "AuraTacticalClient/5.0"}
                )
                with urllib.request.urlopen(req, timeout=4.0) as resp:
                    if resp.status == 200:
                        cloud_db = json.loads(resp.read().decode("utf-8"))
                        keys_db = cloud_db.get("KEYS", {})
                        if key in keys_db:
                            entry = keys_db[key]
                            stored_hwid = entry.get("hwid")
                            if stored_hwid and stored_hwid != self.hwid:
                                return False, "HWID MISMATCH: This key is locked to another computer!", ""
                            
                            tier = entry.get("tier", "LIFETIME PRO")
                            days = entry.get("days", None)
                            self.save_cache(key, tier, self.hwid, remember, days=days)
                            return True, f"Verified via Cloud: {tier}", "Cloud Auth OK"
                        else:
                            return False, "INVALID KEY: License key not found on server.", ""
            except Exception as e:
                # If network fails, fall back to cryptographic verification
                pass

        # C. Cryptographic Signed Key Validation (Offline / Standalone Protection)
        if verify_cryptographic_signature(key):
            if "5DAY" in key:
                tier = "5-DAY VIP TRIAL"
                days = 5
            elif "LIFE" in key:
                tier = "LIFETIME PRO"
                days = None
            else:
                tier = "30-DAY PASS"
                days = 30
            
            # Verify HWID lock if previously bound
            if self.cached_auth.get("activated") and self.cached_auth.get("license_key") == key:
                bound_hwid = self.cached_auth.get("hwid")
                if bound_hwid and bound_hwid != self.hwid:
                    return False, "HWID LOCK: License belongs to a different PC hardware!", ""

            self.save_cache(key, tier, self.hwid, remember, days=days)
            return True, f"Signature Verified: {tier}", "Hardware Bound"

        return False, "INVALID LICENSE: Key rejected by authentication system.", ""

    def is_already_activated(self) -> bool:
        if self.cached_auth.get("activated", False) and self.cached_auth.get("remember", True):
            k = self.cached_auth.get("license_key", "")
            h = self.cached_auth.get("hwid", "")
            exp = self.cached_auth.get("expires_at")
            if exp and time.time() > exp:
                return False  # Expired
            if k and h == self.hwid:
                return True
        return False

    def get_user_tier(self) -> str:
        tier = self.cached_auth.get("tier", "LIFETIME PRO")
        exp = self.cached_auth.get("expires_at")
        if exp:
            rem = max(0, exp - time.time())
            days = int(rem // 86400)
            hours = int((rem % 86400) // 3600)
            if days > 0:
                return f"{tier} ({days}d {hours}h)"
            else:
                mins = int((rem % 3600) // 60)
                return f"{tier} ({hours}h {mins}m)"
        return tier
