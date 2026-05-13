"""QR code generator — returns a PNG for any URL.

Used by the admin dashboard to print/share an onboarding poster that, when
scanned, opens the chat app and lets users install the PWA.
"""
import io

import qrcode
from fastapi import APIRouter, Query
from fastapi.responses import Response
from qrcode.constants import ERROR_CORRECT_H

router = APIRouter(prefix="/qr", tags=["qr"])


@router.get("")
def generate_qr(
    url: str = Query(..., min_length=1, max_length=2048),
    size: int = Query(10, ge=4, le=40, description="Box size in px (each module)"),
    border: int = Query(2, ge=0, le=10),
):
    """Return a PNG QR code encoding the given URL."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0c2e82", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
