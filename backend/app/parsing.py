import re
from datetime import date
from .schemas import TireFields

BRANDS = (
    "MICHELIN",
    "BRIDGESTONE",
    "GOODYEAR",
    "CONTINENTAL",
    "PIRELLI",
    "DUNLOP",
    "YOKOHAMA",
    "HANKOOK",
    "TOYO",
    "FALKEN",
    "NOKIAN",
    "KUMHO",
    "CEAT",
    "MAXXIS",
)
SIZE = re.compile(
    r"(?<!\d)(\d{3})\s*/\s*(\d{2})\s*([RDB])\s*(\d{2})(?:\s+(\d{2,3})(?:/\d{2,3})?\s*([A-Z]))?(?!\d)"
)


def parse_fields(text: str):
    text = text.upper()
    values = {}
    warnings = []
    brands = [b for b in BRANDS if re.search(r"\b" + b + r"\b", text)]
    if len(brands) == 1:
        values["brand"] = brands[0]
    elif len(brands) > 1:
        warnings.append("Multiple brand names found; verify manually.")
    sizes = list(SIZE.finditer(text))
    unique = {m.group(0) for m in sizes}
    if len(unique) == 1:
        m = sizes[0]
        values.update(
            width_mm=int(m[1]),
            aspect_ratio=int(m[2]),
            construction={"R": "radial", "D": "diagonal", "B": "belted"}[m[3]],
            rim_inches=int(m[4]),
        )
        if m[5]:
            values.update(load_index=int(m[5]), speed_rating=m[6])
    elif sizes:
        warnings.append("Multiple tire sizes found; size fields require review.")
    else:
        warnings.append(
            "No supported tire size found. Missing values are not inferred."
        )
    # DOT must be on the same OCR line, and the date must terminate that line.
    dots = re.findall(r"\bDOT[ \t]+([A-Z0-9][A-Z0-9 \t]{3,45})", text)
    if len(dots) == 1:
        code = dots[0].strip()
        values["dot_code"] = "DOT " + code
        dm = re.search(r"(?:^|[ \t])([0-9]{2})([0-9]{2})$", code)
        if dm:
            week, year = int(dm[1]), 2000 + int(dm[2])
            now = date.today()
            this_week = now.isocalendar().week
            if 1 <= week <= 53 and (
                year < now.year or (year == now.year and week <= this_week)
            ):
                values.update(manufacture_week=week, manufacture_year=year)
            else:
                warnings.append(
                    "DOT date candidate is invalid or in the future; date not accepted."
                )
        else:
            warnings.append(
                "DOT text found, but no context-supported four-digit terminal date code."
            )
    elif len(dots) > 1:
        warnings.append("Multiple DOT codes found; verify manually.")
    valid = {}
    for key, value in values.items():
        try:
            TireFields(**{key: value})
            valid[key] = value
        except ValueError:
            warnings.append(f"{key} is outside supported parser limits.")
    warnings.append(
        "Parsing validity is separate from OCR confidence. Confirm fields against the photo; sidewall text does not establish condition or safety."
    )
    return TireFields(**valid), warnings
