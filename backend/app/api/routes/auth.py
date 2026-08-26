from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.services.google_oauth_store import clear_oauth_session, oauth_session, save_oauth_session

router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
]

GOOGLE_ADS_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/adwords",
]


def _build_google_auth_url(scopes: list[str], state: str, login_hint: str | None = None) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": str(settings.GOOGLE_REDIRECT_URI),
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
    }
    if "https://www.googleapis.com/auth/adwords" in scopes:
        params["access_type"] = "offline"
        # Start a fresh account/consent flow. Reusing previously granted scopes can
        # pull unrelated legacy grants into the request and make Google's consent
        # page reject the request before it reaches our callback.
        params["prompt"] = "select_account consent"
    if login_hint:
        params["login_hint"] = login_hint.strip()
    query = urlencode(params, quote_via=quote)
    return f"{GOOGLE_AUTH_URL}?{query}"


def _frontend_redirect(**params: str) -> str:
    separator = "&" if "?" in settings.FRONTEND_URL else "?"
    return f"{settings.FRONTEND_URL}{separator}{urlencode(params, quote_via=quote)}"


@router.get("/google/login")
async def google_login():
    configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    if not configured:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?login=demo")

    return RedirectResponse(url=_build_google_auth_url(GOOGLE_SCOPES, "google-login-local"))


@router.get("/google/connect-ads")
async def google_connect_ads(login_hint: str | None = None):
    configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    if not configured:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?login=demo")
    return RedirectResponse(url=_build_google_auth_url(GOOGLE_ADS_SCOPES, "google-ads-connect-local", login_hint))


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    if error:
        clear_oauth_session()
        message = error_description or (
            "Google đã từ chối quyền truy cập. Hãy dùng Gmail có quyền với tài khoản Manager và cấp quyền Google Ads."
        )
        return RedirectResponse(url=_frontend_redirect(oauth_error=message))
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")

    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": str(settings.GOOGLE_REDIRECT_URI),
                "grant_type": "authorization_code",
            },
        )
        if token_response.status_code >= 400:
            raise HTTPException(status_code=400, detail=token_response.text)

        token_data = token_response.json()
        user_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        user_response.raise_for_status()
        user = user_response.json()

    oauth_session["token"] = token_data
    oauth_session["user"] = {
        "name": user.get("name", "Google User"),
        "email": user.get("email", ""),
        "picture": user.get("picture", ""),
    }
    oauth_session["scopes"] = token_data.get("scope", "")
    save_oauth_session()

    return RedirectResponse(url=_frontend_redirect(google_ads_connected="1"))


@router.get("/me")
async def me():
    if oauth_session["user"]:
        return {
            **oauth_session["user"],
            "google_ads_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
            "google_ads_connected": True,
        }
    return {"id": 1, "name": "Demo Advertiser", "email": "demo@example.com", "google_ads_customer_id": "123-456-7890"}
