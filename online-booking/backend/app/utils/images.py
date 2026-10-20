"""Upload image downscale — avatars and certificates.

Phone photos (3-5MB) would eat the 10GB VDS disk at scale
(11k users x ~0.5MB ≈ 5GB even after this; without it up to 55GB).
Downscale to a 1024px bounding box, JPEG/WebP quality 82, PNG optimized.

iPhone photos arrive as HEIC/HEIF far more often than JPEG. Pillow cannot
decode them on its own, so pillow-heif registers a HEIF opener here. We also
re-encode every upload (which strips EXIF/GPS metadata) and honour the EXIF
orientation — phone portraits otherwise appear sideways on the site.
"""
from io import BytesIO
from typing import Optional

MAX_SIDE_PX = 1024
JPEG_QUALITY = 82
# A 15MB HEIC may decode to a huge canvas. Reject obvious decompression
# bombs before Pillow allocates the full bitmap.
MAX_SOURCE_PIXELS = 60_000_000

_HEIF_REGISTERED = False


def _register_heif_once() -> None:
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    _HEIF_REGISTERED = True
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except ImportError:  # pragma: no cover - requirement is pinned, but keep
        # uploads working for JPEG/PNG/WebP if the wheel is unavailable.
        pass


def _flatten_for_jpeg(img):
    from PIL import Image

    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def downscale_image(data: bytes, content_type: Optional[str] = None) -> tuple[bytes, str]:
    """Validate, orient and downscale an uploaded image.

    ``content_type`` is intentionally only advisory: iOS sometimes reports
    ``image/heic``, a generic type, or an empty string. The real format is
    sniffed by Pillow. Returns ``(bytes, extension)``.

    Raises ``ValueError`` for anything Pillow cannot decode, so callers can
    reject the upload instead of storing a spoofed non-image payload.
    """
    from PIL import Image, ImageOps

    _register_heif_once()
    try:
        img = Image.open(BytesIO(data))
        source_format = (img.format or "").upper()
        if img.width * img.height > MAX_SOURCE_PIXELS:
            raise ValueError("image dimensions are too large")
        # Force a full decode now: an invalid/truncated payload must fail
        # before a file with an image extension reaches the static folder.
        img.load()
        img = ImageOps.exif_transpose(img)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("unsupported or corrupt image") from exc

    if max(img.size) > MAX_SIDE_PX:
        img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.LANCZOS)

    out = BytesIO()
    if source_format == "PNG":
        if img.mode not in ("RGB", "RGBA", "L", "LA", "P", "I;16"):
            img = img.convert("RGBA")
        img.save(out, format="PNG", optimize=True)
        return out.getvalue(), ".png"
    if source_format == "WEBP":
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.save(out, format="WEBP", quality=JPEG_QUALITY, method=6)
        return out.getvalue(), ".webp"

    # JPEG, HEIC/HEIF, AVIF and every other phone format become a broadly
    # supported JPEG. This also flattens transparency onto white.
    img = _flatten_for_jpeg(img)
    img.save(out, format="JPEG", quality=JPEG_QUALITY,
             optimize=True, progressive=True)
    return out.getvalue(), ".jpg"
