"""
Meta / Instagram OAuth 2.0 flow.

Flow:
  1. GET /api/oauth/connect/{brand_slug}  → redirect to Facebook OAuth dialog
  2. User logs in + approves permissions on Facebook
  3. GET /api/oauth/callback?code=...&state={brand_slug}
       → exchanges short-lived code for long-lived token (60 days)
       → fetches Facebook Pages → finds linked Instagram Business Account ID
       → saves credentials to brand_profile.json
       → redirects to UI with success message

Token refresh:
  Long-lived tokens last 60 days. A background job checks daily and refreshes
  any token expiring within 7 days.

Docs:
  https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow
  https://developers.facebook.com/docs/instagram-api/getting-started
"""

import json
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests

from config.settings import META_APP_ID, META_APP_SECRET, STORAGE_DIR, BRAND_PROFILES_DIR

GRAPH_URL = "https://graph.facebook.com/v19.0"

OAUTH_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_comments",
    "instagram_manage_insights",
    "pages_read_engagement",
    "pages_manage_posts",
]


# ════════════════════════════════════════════════════════════════════════════
# OAuth URL builder
# ════════════════════════════════════════════════════════════════════════════

def get_oauth_url(brand_slug: str, redirect_uri: str) -> str:
    """Build the Facebook OAuth dialog URL for a given brand."""
    params = {
        "client_id": META_APP_ID,
        "redirect_uri": redirect_uri,
        "scope": ",".join(OAUTH_SCOPES),
        "state": brand_slug,
        "response_type": "code",
    }
    return f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"


# ════════════════════════════════════════════════════════════════════════════
# Token exchange
# ════════════════════════════════════════════════════════════════════════════

def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    """
    Exchange an authorization code for a long-lived access token.
    Step 1: code → short-lived token (1 hour)
    Step 2: short-lived → long-lived token (60 days)
    """
    # Step 1 — short-lived token
    r = requests.get(f"{GRAPH_URL}/oauth/access_token", params={
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "redirect_uri": redirect_uri,
        "code": code,
    }, timeout=20)
    r.raise_for_status()
    short = r.json()
    short_token = short.get("access_token")
    if not short_token:
        raise ValueError(f"Token exchange failed: {short.get('error', {}).get('message', short)}")

    # Step 2 — long-lived token
    r2 = requests.get(f"{GRAPH_URL}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "fb_exchange_token": short_token,
    }, timeout=20)
    r2.raise_for_status()
    long = r2.json()
    long_token = long.get("access_token", short_token)
    expires_in = long.get("expires_in", 60 * 24 * 3600)  # default 60 days
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    return {
        "access_token": long_token,
        "expires_at": expires_at.isoformat(),
        "expires_in_days": expires_in // 86400,
    }


def refresh_long_lived_token(token: str) -> dict:
    """Refresh a long-lived token to extend it by another 60 days."""
    r = requests.get(f"{GRAPH_URL}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "fb_exchange_token": token,
    }, timeout=20)
    r.raise_for_status()
    data = r.json()
    expires_in = data.get("expires_in", 60 * 24 * 3600)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    return {
        "access_token": data.get("access_token", token),
        "expires_at": expires_at.isoformat(),
        "expires_in_days": expires_in // 86400,
    }


# ════════════════════════════════════════════════════════════════════════════
# Instagram account discovery
# ════════════════════════════════════════════════════════════════════════════

def fetch_instagram_account(token: str) -> dict:
    """
    Given a user access token, find the Instagram Business Account ID by:
      1. GET /me/accounts  → list of FB Pages the user manages
      2. GET /{page_id}?fields=instagram_business_account  → linked IG account
    Returns the first IG Business Account found.
    """
    r = requests.get(f"{GRAPH_URL}/me/accounts", params={
        "access_token": token,
        "fields": "id,name,access_token",
    }, timeout=20)
    r.raise_for_status()
    pages = r.json().get("data", [])

    if not pages:
        raise ValueError(
            "No Facebook Pages found for this account. "
            "Make sure you manage a Facebook Page that is linked to your Instagram account."
        )

    for page in pages:
        page_id = page["id"]
        page_token = page.get("access_token", token)
        r2 = requests.get(f"{GRAPH_URL}/{page_id}", params={
            "fields": "instagram_business_account",
            "access_token": page_token,
        }, timeout=20)
        data = r2.json()
        ig = data.get("instagram_business_account")
        if ig:
            return {
                "instagram_account_id": ig["id"],
                "facebook_page_id": page_id,
                "facebook_page_name": page.get("name", ""),
            }

    raise ValueError(
        "No Instagram Business Account linked to any of your Facebook Pages. "
        "To fix: Instagram app → Settings → Account → Switch to Professional Account, "
        "then link it to a Facebook Page."
    )


# ════════════════════════════════════════════════════════════════════════════
# Credential storage
# ════════════════════════════════════════════════════════════════════════════

def save_credentials_to_brand(brand_slug: str, token_data: dict, account_data: dict) -> None:
    """
    Merge OAuth credentials into a brand's stored profile.
    If the brand only exists as a built-in profile (not yet in storage),
    it is copied to storage first.
    """
    from storage.data_store import _slug, DataStore

    profile_path = STORAGE_DIR / brand_slug / "brand_profile.json"

    # If not in storage yet, look for it in built-in profiles and copy it
    if not profile_path.exists():
        found = None
        for path in BRAND_PROFILES_DIR.glob("*.json"):
            try:
                p = json.loads(path.read_text())
                if _slug(p.get("name", "")) == brand_slug or path.stem == brand_slug:
                    found = p
                    break
            except Exception:
                pass
        if not found:
            raise FileNotFoundError(
                f"Brand '{brand_slug}' not found in storage or built-in profiles. "
                "Save the brand first before connecting Instagram."
            )
        # Save it to storage so we can attach credentials
        DataStore(found["name"]).save_brand_profile(found)

    profile = json.loads(profile_path.read_text())

    profile["meta_credentials"] = {
        "access_token": token_data["access_token"],
        "instagram_account_id": account_data["instagram_account_id"],
        "facebook_page_id": account_data["facebook_page_id"],
        "facebook_page_name": account_data.get("facebook_page_name", ""),
        "expires_at": token_data.get("expires_at", ""),
        "expires_in_days": token_data.get("expires_in_days", 60),
        "connected_at": datetime.utcnow().isoformat(),
    }
    # Top-level aliases for backward compatibility
    profile["instagram_account_id"] = account_data["instagram_account_id"]
    profile["facebook_page_id"] = account_data["facebook_page_id"]

    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2))


# ════════════════════════════════════════════════════════════════════════════
# Token status helpers
# ════════════════════════════════════════════════════════════════════════════

def get_token_status(brand_profile: dict) -> dict:
    """
    Return the OAuth connection status for a brand.
    Statuses: not_connected | connected | expiring_soon | expired
    """
    creds = brand_profile.get("meta_credentials", {})
    token = creds.get("access_token") or brand_profile.get("meta_access_token")
    ig_id = (creds.get("instagram_account_id")
             or brand_profile.get("instagram_account_id")
             or brand_profile.get("instagram_business_account_id"))

    if not token or not ig_id:
        return {"status": "not_connected", "label": "Not Connected", "ig_account_id": None}

    expires_at_str = creds.get("expires_at") or brand_profile.get("token_expires_at")
    days_left = None
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            days_left = (expires_at - datetime.utcnow()).days
            if days_left < 0:
                return {
                    "status": "expired",
                    "label": "Token Expired — Reconnect",
                    "days_left": 0,
                    "ig_account_id": ig_id,
                }
            elif days_left <= 7:
                return {
                    "status": "expiring_soon",
                    "label": f"Expiring in {days_left}d",
                    "days_left": days_left,
                    "ig_account_id": ig_id,
                }
            else:
                return {
                    "status": "connected",
                    "label": f"Connected · {days_left}d left",
                    "days_left": days_left,
                    "ig_account_id": ig_id,
                }
        except Exception:
            pass

    return {
        "status": "connected",
        "label": "Connected",
        "days_left": days_left,
        "ig_account_id": ig_id,
    }


# ════════════════════════════════════════════════════════════════════════════
# Token refresh (called by background scheduler)
# ════════════════════════════════════════════════════════════════════════════

def refresh_all_expiring_tokens(glog_fn=None) -> list[str]:
    """
    Scan all stored brand profiles. Refresh tokens expiring in <=7 days.
    Returns list of brand slugs that were refreshed.
    """
    from storage.data_store import _slug

    refreshed = []

    if not STORAGE_DIR.exists():
        return refreshed

    for brand_dir in STORAGE_DIR.iterdir():
        profile_path = brand_dir / "brand_profile.json"
        if not profile_path.exists():
            continue
        try:
            profile = json.loads(profile_path.read_text())
            status = get_token_status(profile)
            if status["status"] in ("expiring_soon", "expired"):
                creds = profile.get("meta_credentials", {})
                old_token = creds.get("access_token")
                if not old_token:
                    continue
                try:
                    new_token_data = refresh_long_lived_token(old_token)
                    creds["access_token"] = new_token_data["access_token"]
                    creds["expires_at"] = new_token_data["expires_at"]
                    creds["expires_in_days"] = new_token_data.get("expires_in_days", 60)
                    profile["meta_credentials"] = creds
                    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
                    refreshed.append(brand_dir.name)
                    if glog_fn:
                        glog_fn(f"Token refreshed for brand '{brand_dir.name}' — "
                                f"expires in {new_token_data.get('expires_in_days', 60)}d")
                except Exception as e:
                    if glog_fn:
                        glog_fn(f"Token refresh FAILED for brand '{brand_dir.name}': {e}")
        except Exception:
            continue

    return refreshed
