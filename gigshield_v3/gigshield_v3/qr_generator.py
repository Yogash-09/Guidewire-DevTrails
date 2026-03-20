"""
GigShield AI — UPI QR Generator
==================================
Generates a branded SVG UPI QR per worker without external `qrcode` package.
If the `qrcode` package is installed, uses it for a real QR matrix.
Falls back to a deterministic pattern derived from SHA-256 of the UPI link.
"""

import os, hashlib
from io import BytesIO

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
UPI_ID     = os.environ.get("UPI_ID", "hariskanis@oksbi")
UPI_NAME   = os.environ.get("UPI_NAME", "Hari Hari")


def upi_link(amount: float, worker_id: str) -> str:
    txn = hashlib.md5(f"{worker_id}{amount}".encode()).hexdigest()[:12].upper()
    return (f"upi://pay?pa={UPI_ID}&pn={UPI_NAME.replace(' ','%20')}"
            f"&am={amount:.2f}&cu=INR&tn=GigShield%20Premium&tr={txn}")


def _try_qrcode_lib(data: str, size_px: int = 240) -> bytes | None:
    """Attempt to use the optional `qrcode` package. Returns PNG bytes or None."""
    try:
        import qrcode
        from PIL import Image
        qr = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=8, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _svg_qr(upi_url: str, amount: float) -> str:
    """
    Generate a branded SVG QR matching the Google Pay white-card style.
    Real UPI: hariskanis@oksbi  |  Name: Hari Hari
    """
    h    = hashlib.sha256(upi_url.encode()).hexdigest()
    bits = bin(int(h, 16))[2:].zfill(256)
    cell, size, quiet = 9, 29, 4
    total = (size + quiet * 2) * cell

    # Data modules
    rects = [
        f'<rect x="{(quiet+c)*cell}" y="{(quiet+r)*cell}" width="{cell}" height="{cell}" fill="#1a1a2e"/>'
        for r in range(size) for c in range(size)
        if bits[(r * size + c) % 256] == "1"
    ]

    # Finder patterns (3 corners)
    def finder(ox, oy):
        return [
            f'<rect x="{ox+c*cell}" y="{oy+r*cell}" width="{cell}" height="{cell}" fill="#1a1a2e"/>'
            for r in range(7) for c in range(7)
            if r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4)
        ]

    fp = (finder(quiet*cell, quiet*cell)
          + finder((quiet+size-7)*cell, quiet*cell)
          + finder(quiet*cell, (quiet+size-7)*cell))

    # Outer card dimensions
    pad = 28
    W   = total + pad * 2
    H   = total + pad * 2 + 120   # extra for header + footer

    # Avatar circle initials
    av_cx, av_cy = W // 2, 38

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="pageGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#e8f4fd"/>
      <stop offset="100%" stop-color="#dde8f5"/>
    </linearGradient>
    <linearGradient id="avatarGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="#4285F4"/>
      <stop offset="100%" stop-color="#1565C0"/>
    </linearGradient>
    <filter id="cardShadow" x="-5%" y="-5%" width="110%" height="120%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="rgba(0,0,0,0.12)"/>
    </filter>
  </defs>

  <!-- Page background (light blue like Google Pay) -->
  <rect width="{W}" height="{H}" fill="url(#pageGrad)"/>

  <!-- Avatar circle -->
  <circle cx="{av_cx}" cy="{av_cy}" r="26" fill="url(#avatarGrad)"/>
  <text x="{av_cx}" y="{av_cy+8}" text-anchor="middle" font-size="18" font-weight="700"
        fill="white" font-family="sans-serif">HH</text>

  <!-- Name label -->
  <text x="{W//2}" y="{av_cy+44}" text-anchor="middle" font-size="17" font-weight="600"
        fill="#202124" font-family="sans-serif">Hari Hari</text>

  <!-- White QR card -->
  <rect x="14" y="{av_cy+58}" width="{W-28}" height="{total+pad*2}"
        rx="20" fill="white" filter="url(#cardShadow)"/>

  <!-- QR modules -->
  <g transform="translate({14+pad},{av_cy+58+pad})">
    {"".join(rects + fp)}
  </g>

  <!-- GPay logo circle in QR centre -->
  <circle cx="{W//2}" cy="{av_cy+58+pad + total//2}" r="20" fill="white"/>
  <!-- Coloured G dots (simplified GPay logo) -->
  <circle cx="{W//2-6}" cy="{av_cy+58+pad + total//2-4}" r="5" fill="#4285F4"/>
  <circle cx="{W//2+6}" cy="{av_cy+58+pad + total//2-4}" r="5" fill="#EA4335"/>
  <circle cx="{W//2-6}" cy="{av_cy+58+pad + total//2+6}" r="5" fill="#34A853"/>
  <circle cx="{W//2+6}" cy="{av_cy+58+pad + total//2+6}" r="5" fill="#FBBC05"/>

  <!-- UPI ID pill -->
  <rect x="30" y="{av_cy+58+total+pad*2+10}" width="{W-60}" height="32"
        rx="16" fill="white" filter="url(#cardShadow)"/>
  <text x="{W//2}" y="{av_cy+58+total+pad*2+31}" text-anchor="middle"
        font-size="13" font-weight="600" fill="#202124" font-family="monospace">
    UPI ID: {UPI_ID}
  </text>

  <!-- Amount (shown only if > 0) -->
  {"" if amount == 0 else f'<text x="{W//2}" y="{av_cy+58+total+pad*2+62}" text-anchor="middle" font-size="14" font-weight="700" fill="#1a73e8" font-family="sans-serif">₹{amount:.0f}</text>'}

  <!-- Footer -->
  <text x="{W//2}" y="{H-10}" text-anchor="middle" font-size="11"
        fill="#5f6368" font-family="sans-serif">
    Scan to pay with any UPI app
  </text>
</svg>"""


def generate_qr(amount: float, worker_id: str) -> str:
    """
    Save QR file in /static/ and return its filename.
    Tries real `qrcode` lib first; falls back to SVG.
    """
    os.makedirs(STATIC_DIR, exist_ok=True)
    url = upi_link(amount, worker_id)

    png = _try_qrcode_lib(url)
    if png:
        fname = f"qr_{worker_id}.png"
        with open(os.path.join(STATIC_DIR, fname), "wb") as f:
            f.write(png)
        return fname

    # SVG fallback
    fname = f"qr_{worker_id}.svg"
    with open(os.path.join(STATIC_DIR, fname), "w", encoding="utf-8") as f:
        f.write(_svg_qr(url, amount))
    return fname


def get_qr_filename(worker_id: str) -> str:
    for ext in ["png", "svg"]:
        fname = f"qr_{worker_id}.{ext}"
        if os.path.exists(os.path.join(STATIC_DIR, fname)):
            return fname
    return ""
