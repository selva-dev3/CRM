"""Real Meta transport. Ambiguous POST outcomes must never be blindly retried."""

import base64
import hashlib
import hmac
import re
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.errors import APIException


def matches_media_sha256(content: bytes, expected: str) -> bool:
    digest = hashlib.sha256(content).digest()
    expected = expected.strip()
    return hmac.compare_digest(digest.hex(), expected.casefold()) or hmac.compare_digest(
        base64.b64encode(digest).decode(), expected
    )


class WhatsAppProviderService:
    def __init__(self, access_token: str, api_version: str) -> None:
        if not re.fullmatch(r"v\d{2}\.0", api_version):
            raise ValueError("Invalid Graph API version")
        self.access_token = access_token
        # Fixed provider host prevents administrator-controlled SSRF/token exfiltration.
        self.base_url = f"https://graph.facebook.com/{api_version}"

    async def request(
        self, method: str, resource: str, *, payload: dict | None = None, params: dict | None = None
    ) -> dict:
        if not re.fullmatch(
            r"\d{1,100}(?:/(?:messages|phone_numbers|message_templates))?", resource
        ):
            raise ValueError("Invalid provider resource")
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=5), follow_redirects=False
        ) as client:
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}/{resource}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    json=payload,
                    params=params,
                )
            except httpx.HTTPError as exc:
                raise APIException(
                    message="Provider outcome is unknown; do not resend automatically.",
                    code="WHATSAPP_OUTCOME_UNKNOWN",
                    status_code=503,
                ) from exc
        if response.status_code >= 500:
            raise APIException(
                message="Provider outcome is unknown; review required.",
                code="WHATSAPP_OUTCOME_UNKNOWN",
                status_code=503,
            )
        if not response.is_success:
            # Never persist provider messages: they can contain tokens or customer text.
            raise APIException(
                message="WhatsApp rejected the request.",
                code=f"WHATSAPP_PROVIDER_{response.status_code}",
                status_code=502,
            )
        try:
            result = response.json()
        except ValueError as exc:
            raise APIException(
                message="Provider outcome is unknown.",
                code="WHATSAPP_OUTCOME_UNKNOWN",
                status_code=503,
            ) from exc
        if not isinstance(result, dict):
            raise APIException(
                message="Invalid provider response.",
                code="WHATSAPP_OUTCOME_UNKNOWN",
                status_code=503,
            )
        return result

    async def send_text(self, phone_id: str, recipient: str, body: str, correlation_id: str) -> str:
        data = await self.request(
            "POST",
            f"{phone_id}/messages",
            payload={
                "messaging_product": "whatsapp",
                "to": recipient.lstrip("+"),
                "type": "text",
                "text": {"body": body, "preview_url": False},
                "biz_opaque_callback_data": correlation_id,
            },
        )
        messages = data.get("messages")
        provider_id = (
            messages[0].get("id")
            if isinstance(messages, list) and messages and isinstance(messages[0], dict)
            else None
        )
        if not isinstance(provider_id, str) or not 1 <= len(provider_id) <= 255:
            raise APIException(
                message="Provider outcome is unknown.",
                code="WHATSAPP_OUTCOME_UNKNOWN",
                status_code=503,
            )
        return provider_id

    async def send_template(
        self,
        phone_id: str,
        recipient: str,
        name: str,
        language: str,
        parameters: list[str],
        correlation_id: str,
    ) -> str:
        components = []
        if parameters:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": value} for value in parameters],
                }
            )
        data = await self.request(
            "POST",
            f"{phone_id}/messages",
            payload={
                "messaging_product": "whatsapp",
                "to": recipient.lstrip("+"),
                "type": "template",
                "template": {
                    "name": name,
                    "language": {"code": language},
                    "components": components,
                },
                "biz_opaque_callback_data": correlation_id,
            },
        )
        messages = data.get("messages")
        provider_id = (
            messages[0].get("id")
            if isinstance(messages, list) and messages and isinstance(messages[0], dict)
            else None
        )
        if not isinstance(provider_id, str) or not 1 <= len(provider_id) <= 255:
            raise APIException(
                message="Provider outcome is unknown.",
                code="WHATSAPP_OUTCOME_UNKNOWN",
                status_code=503,
            )
        return provider_id

    async def download_media(self, media_id: str, expected_sha256: str | None) -> tuple[bytes, str]:
        metadata = await self.request("GET", media_id)
        url = metadata.get("url")
        mime_type = metadata.get("mime_type", "application/octet-stream")
        size = metadata.get("file_size")
        if (
            not isinstance(url, str)
            or not isinstance(mime_type, str)
            or not re.fullmatch(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+", mime_type)
        ):
            raise APIException(
                message="Invalid media metadata.", code="WHATSAPP_MEDIA_INVALID", status_code=502
            )
        parsed = urlparse(url)
        allowed = (
            parsed.scheme == "https"
            and parsed.hostname
            and any(
                parsed.hostname == host or parsed.hostname.endswith("." + host)
                for host in ("facebook.com", "fbsbx.com", "fbcdn.net")
            )
        )
        if not allowed:
            raise APIException(
                message="Invalid media location.", code="WHATSAPP_MEDIA_INVALID", status_code=502
            )
        if size is not None and (
            not str(size).isdigit() or int(size) > settings.WHATSAPP_MEDIA_MAX_BYTES
        ):
            raise APIException(
                message="WhatsApp media is too large.",
                code="WHATSAPP_MEDIA_TOO_LARGE",
                status_code=413,
            )
        content = bytearray()
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30, connect=5), follow_redirects=False
        ) as client:
            try:
                async with client.stream(
                    "GET", url, headers={"Authorization": f"Bearer {self.access_token}"}
                ) as response:
                    if not response.is_success:
                        raise APIException(
                            message="WhatsApp media is unavailable.",
                            code="WHATSAPP_MEDIA_UNAVAILABLE",
                            status_code=502,
                        )
                    async for chunk in response.aiter_bytes():
                        if len(content) + len(chunk) > settings.WHATSAPP_MEDIA_MAX_BYTES:
                            raise APIException(
                                message="WhatsApp media is too large.",
                                code="WHATSAPP_MEDIA_TOO_LARGE",
                                status_code=413,
                            )
                        content.extend(chunk)
            except httpx.HTTPError as exc:
                raise APIException(
                    message="WhatsApp media is unavailable.",
                    code="WHATSAPP_MEDIA_UNAVAILABLE",
                    status_code=502,
                ) from exc
        if expected_sha256 and not matches_media_sha256(content, expected_sha256):
            raise APIException(
                message="WhatsApp media integrity check failed.",
                code="WHATSAPP_MEDIA_INVALID",
                status_code=502,
            )
        return bytes(content), mime_type[:100]
