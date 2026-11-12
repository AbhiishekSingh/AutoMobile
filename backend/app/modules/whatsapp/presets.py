"""Google review / KTM app / Instagram links for the dealership's showrooms, matched to branches by name or city."""
KTM_APP = "https://play.google.com/store/apps/details?id=com.excellonsoft.bajajcarektm"
PRESET = {
    "thane": {"GOOGLE_REVIEW_URL": "https://share.google/SIifB404QclXVvqk4", "INSTAGRAM_URL": "https://www.instagram.com/ktm__thane?igsh=MXQ1M2s3ZTBqOHN6dw=="},
    "nerul": {"GOOGLE_REVIEW_URL": "https://share.google/f7lC5VXoufzpqeYyN", "INSTAGRAM_URL": "https://www.instagram.com/ktm__nerul?igsh=MXdheDVjcnI4bjg1bw=="},
    "bhiwandi": {"GOOGLE_REVIEW_URL": "https://share.google/xXf8q8A9BSBk85cx3", "INSTAGRAM_URL": "https://www.instagram.com/ktm__bhiwandi?igsh=MTZhcWVucXU5ZmQzNg=="},
    "ulhasnagar": {"GOOGLE_REVIEW_URL": "https://share.google/egcb3xEPiEWkzzCxY", "INSTAGRAM_URL": "https://www.instagram.com/ktm__ulhasnagar?igsh=MTd3ZmN3dHJrZGt1Yg=="},
    "chembur": {"GOOGLE_REVIEW_URL": "https://share.google/ejSzqgqih4KKwMQn3", "INSTAGRAM_URL": "https://www.instagram.com/ktm__chembur?igsh=MWR1c3cwamFtbnEzcA=="},
    "dombivli": {"GOOGLE_REVIEW_URL": "https://share.google/0JPX11poiyzitHRSI", "INSTAGRAM_URL": "https://www.instagram.com/ktm__dombivali"},
}
ALIASES = {"dombivali": "dombivli", "dombivilli": "dombivli", "ulhasnagar": "ulhasnagar", "ulhas nagar": "ulhasnagar"}


def match(branch) -> str | None:
    text = f"{branch.name or ''} {branch.city or ''}".lower()
    for alias, key in ALIASES.items():
        if alias in text:
            return key
    for key in PRESET:
        if key in text:
            return key
    return None
