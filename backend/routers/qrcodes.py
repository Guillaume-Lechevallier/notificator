import io

import segno
from fastapi import APIRouter, HTTPException, Query, Response

router = APIRouter(prefix="/api/qrcodes", tags=["qrcodes"])


@router.get("/enrollment", response_class=Response)
def enrollment_qr(url: str = Query(..., min_length=1, max_length=2048)):
    try:
        qr = segno.make(url, error="m")
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise HTTPException(status_code=400, detail="Lien invalide pour le QR code") from exc

    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", border=2, scale=6)

    raw_payload = buffer.getvalue()
    svg_payload = raw_payload.decode("utf-8") if isinstance(raw_payload, (bytes, bytearray)) else str(raw_payload)

    if not svg_payload:
        raise HTTPException(status_code=500, detail="Génération du QR code impossible")

    headers = {"Content-Disposition": "inline; filename=enrollment-qr.svg"}
    return Response(content=svg_payload, media_type="image/svg+xml", headers=headers)
