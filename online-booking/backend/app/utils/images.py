"""Upload image downscale — avatars and certificates.

Phone photos (3-5MB) would eat the 10GB VDS disk at scale
(11k users x ~0.5MB ≈ 5GB even after this; without it up to 55GB).
Downscale to a 1024px bounding box, JPEG/WebP quality 82, PNG optimized.
"""
from io import BytesIO

MAX_SIDE_PX = 1024
JPEG_QUALITY = 82


def downscale_image(data: bytes, content_type: str) -> tuple[bytes, str]:
    """Resize to MAX_SIDE_PX box. Returns (bytes, extension)."""
    from PIL import Image

    img = Image.open(BytesIO(data))
    if max(img.size) > MAX_SIDE_PX:
        img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.LANCZOS)
    out = BytesIO()
    if content_type == "image/jpeg":
        rgb = img.convert("RGB") if img.mode in ("RGBA", "P") else img
        rgb.save(out, format="JPEG", quality=JPEG_QUALITY,
                 optimize=True, progressive=True)
        return out.getvalue(), ".jpg"
    if content_type == "image/webp":
        img.save(out, format="WEBP", quality=JPEG_QUALITY, method=6)
        return out.getvalue(), ".webp"
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), ".png"
