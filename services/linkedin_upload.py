from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

_LINKEDIN_VERSION = "202501"
_RESTLI_VERSION = "2.0.0"


def _initialize_upload(
    endpoint: str,
    person_id: str,
    access_token: str,
) -> tuple[str, str]:
    """Register an upload with LinkedIn and return (upload_url, asset_urn).

    *endpoint* is the full URL e.g. ``https://api.linkedin.com/rest/images?action=initializeUpload``.
    Raises ``RuntimeError`` on non-2xx responses.
    """
    resp = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "LinkedIn-Version": _LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": _RESTLI_VERSION,
        },
        json={"initializeUploadRequest": {"owner": f"urn:li:person:{person_id}"}},
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(
            f"LinkedIn upload initialization failed ({endpoint}): "
            f"{resp.status_code} {resp.text}"
        )
    value = resp.json()["value"]
    # Key is "image" for images, "document" for documents — grab whichever is present
    urn: str = value.get("image") or value.get("document") or ""
    return value["uploadUrl"], urn


def upload_image(
    file_bytes: bytes,
    mime_type: str,
    person_id: str,
    access_token: str,
) -> str:
    """Upload an image to LinkedIn and return its asset URN (``urn:li:image:...``).

    Raises ``RuntimeError`` on any non-2xx response.
    """
    upload_url, image_urn = _initialize_upload(
        "https://api.linkedin.com/rest/images?action=initializeUpload",
        person_id,
        access_token,
    )
    logger.info("LinkedIn image upload initialized — urn: %s", image_urn)

    put_resp = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": mime_type},
        data=file_bytes,
        timeout=120,
    )
    if put_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"LinkedIn image binary upload failed: {put_resp.status_code} {put_resp.text}"
        )
    return image_urn


def upload_document(
    file_bytes: bytes,
    filename: str,
    person_id: str,
    access_token: str,
) -> str:
    """Upload a document to LinkedIn and return its asset URN (``urn:li:document:...``).

    Supported formats: PDF, DOCX, PPTX (max 100 MB / 300 pages).
    Raises ``RuntimeError`` on any non-2xx response.
    """
    upload_url, document_urn = _initialize_upload(
        "https://api.linkedin.com/rest/documents?action=initializeUpload",
        person_id,
        access_token,
    )
    logger.info("LinkedIn document upload initialized — urn: %s", document_urn)

    put_resp = requests.put(
        upload_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream",
        },
        data=file_bytes,
        timeout=300,
    )
    if put_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"LinkedIn document binary upload failed: {put_resp.status_code} {put_resp.text}"
        )
    return document_urn
