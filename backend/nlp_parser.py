# nlp_parser.py
# Parses school menu images (grid table) into per-day, per-meal items,
# and also supports plain text parsing for general school circulars.

from typing import List, Optional, Dict, Tuple
from pydantic import BaseModel, Field
from urllib.parse import quote_plus
import re
import io

# Image / OCR
import numpy as np
import cv2
from PIL import Image
import pytesseract

# ------------------------------
# Constants
# ------------------------------

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
MEALS    = ["Breakfast", "AM Snack", "PM Snack"]

DAYS_LOWER = [d.lower() for d in WEEKDAYS] + ["saturday", "sunday"]

FOOD_HINTS = [
    # Breakfast mains
    "waffles", "scrambled eggs", "turkey sausage", "oatmeal",
    "french toast", "ham", "cereal", "fresh fruit", "fruit",
    # Sandwiches & wraps
    "peanut butter and jelly", "pb&j", "grilled cheese", "turkey sandwich",
    "ham sandwich", "chicken sandwich", "wrap", "club sandwich",
    # Mains
    "chicken nuggets", "mac and cheese", "macaroni and cheese", "chicken tenders",
    "mini pizza", "hot dog", "hamburger", "sloppy joe", "pasta salad",
    "burrito", "quesadilla", "taco", "spaghetti",
    # Snacks & sides
    "apple slices", "banana", "orange", "grapes", "strawberries", "blueberries",
    "baby carrots", "celery sticks", "string cheese", "yogurt", "trail mix",
    "granola bar", "granola bars", "pretzels", "crackers", "popcorn",
    "graham crackers", "rice cake", "cream cheese", "peanut butter",
    "sliced peaches", "carrots", "ranch", "beans", "cucumber slices",
    # Drinks / extras
    "milk", "chocolate milk", "juice box", "water bottle", "cookies"
]

SUPPLY_HINTS = [
    "scissors","glue","glue stick","sketch pens","pencils","eraser","sharpener",
    "crayons","color pencils","marker","notebook","ruler","chart paper","craft paper","folder"
]

DRESS_HINTS = ["sports uniform","house uniform","white shoes","costume","traditional dress"]

DATE_REGEX = r"\b(\d{1,2}[/\-]\d{1,2}([/\-]\d{2,4})?)\b"
TIME_REGEX = r"\b(\d{1,2}:\d{2}\s?(AM|PM|am|pm)?)\b"

WEEKDAY_RE = re.compile(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", re.IGNORECASE)

# ------------------------------
# Models
# ------------------------------

class ParsedNote(BaseModel):
    day: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    foods: List[str] = Field(default_factory=list)
    supplies: List[str] = Field(default_factory=list)
    dress_code: Optional[str] = None
    event: Optional[str] = None
    raw_text: str
    # structured per-day output (only filled in image/text fallback modes)
    per_day: Dict[str, Dict[str, List[str]]] = Field(default_factory=dict)

class ParsedMenu(BaseModel):
    per_day: Dict[str, Dict[str, List[str]]] = Field(default_factory=dict)
    all_foods: List[str] = Field(default_factory=list)
    raw_text: str

# ------------------------------
# Normalization & Food Canon
# ------------------------------

_CANON = {
    "granola bars": "Granola Bars",
    "granola bar": "Granola Bars",
    "graham crackers": "Graham Crackers",
    "apple slices": "Apple Slices",
    "string cheese": "String Cheese",
    "peanut butter": "Peanut Butter",
    "cream cheese": "Cream Cheese",
    "rice cake": "Rice Cake",
    "sliced peaches": "Sliced Peaches",
    "fresh fruit": "Fresh Fruit",
    "turkey sausage": "Turkey Sausage",
    "scrambled eggs": "Scrambled Eggs",
    "french toast": "French Toast",
    "oatmeal": "Oatmeal",
    "cereal": "Cereal",
    "yogurt": "Yogurt",
    "crackers": "Crackers",
    "pretzels": "Pretzels",
    "cookies": "Cookies",
    "milk": "2% Milk",  # default if bare "Milk"
}

def _canon_food(s: str) -> str:
    key = s.strip().lower()
    val = _CANON.get(key)
    if val:
        return val
    return s.strip().title()

def _normalize_ocr_text(t: str) -> str:
    s = t
    # Common OCR -> fix to "2% Milk"
    s = re.sub(r"\b[aoO03]\s*%\s*Mi?k\b", "2% Milk", s, flags=re.IGNORECASE)
    s = re.sub(r"\b(\d)\s*%\s*Mi?k\b", r"\1% Milk", s, flags=re.IGNORECASE)
    # Common words
    s = re.sub(r"\bHarn\b", "Ham", s, flags=re.IGNORECASE)
    s = re.sub(r"\bMenday\b", "Monday", s, flags=re.IGNORECASE)
    s = re.sub(r"\bMi\b", "Milk", s, flags=re.IGNORECASE)
    return s

def _strip_weekday_noise(s: str) -> str:
    s = WEEKDAY_RE.sub(" ", s)
    s = s.replace("\n", " ")
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def _looks_like_noise(s: str) -> bool:
    s2 = s.strip()
    if len(s2) < 2:
        return True
    if len(re.sub(r"[A-Za-z]", "", s2)) > len(re.sub(r"[^A-Za-z]", "", s2)):
        return True
    return False

def _maps_search_link(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"

def _doordash_search_link(query: str) -> str:
    return f"https://www.doordash.com/search/store/{quote_plus(query)}"

# ------------------------------
# Food Extraction (text)
# ------------------------------

def _food_patterns() -> List[re.Pattern]:
    pats = []
    for f in FOOD_HINTS:
        pats.append(re.compile(r"\b" + re.escape(f) + r"\b", re.IGNORECASE))
    return pats

FOOD_PATTERNS = _food_patterns()

def _extract_foods_from_text(text: str) -> List[str]:
    text = _normalize_ocr_text(text)
    text = _strip_weekday_noise(text)

    # Split lines and then by "and"/"," to break combined items
    bits: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"\band\b|,", line, flags=re.IGNORECASE)
        bits.extend([p.strip() for p in parts if p.strip()])

    matched: List[str] = []

    # Dictionary matches
    for b in bits:
        if _looks_like_noise(b):
            continue
        for pat in FOOD_PATTERNS:
            m = pat.search(b)
            if m:
                matched.append(m.group(0))
                break

    # Title-Case fallback for menu nouns
    for ph in re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", text):
        if _looks_like_noise(ph):
            continue
        if any(n in ph.lower() for n in [
            "waffle","toast","egg","sausage","oatmeal","cereal","fruit","peach",
            "cracker","graham","cheese","yogurt","pretzel","cookie","grape",
            "peanut","butter","milk","rice","cake","bean","cucumber"
        ]):
            matched.append(ph)

    # Numeric milk like "2% Milk"
    matched.extend(re.findall(r"\b\d+\s*%\s*Milk\b", text, flags=re.IGNORECASE))

    # Canonicalize + dedup (preserve order)
    out, seen = [], set()
    for m in matched:
        c = _canon_food(m)
        k = c.lower()
        if re.fullmatch(r"\d+\s*%\s*milk", c, flags=re.IGNORECASE):
            c = "2% Milk"
            k = c.lower()
        if k not in seen:
            out.append(c)
            seen.add(k)
    return out

# ------------------------------
# Image → Table Parsing
# ------------------------------

def _preprocess_for_grid(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=1.7, fy=1.7, interpolation=cv2.INTER_CUBIC)
    blur = cv2.GaussianBlur(gray, (3,3), 0)
    thr  = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                 cv2.THRESH_BINARY_INV, 31, 10)
    return thr

def _find_cells(bin_img: np.ndarray) -> List[Tuple[int,int,int,int]]:
    rows, cols = bin_img.shape[:2]

    # line detection kernels
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (cols // 30, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, rows // 30))

    # NOTE: op comes before kernel (cv2.MORPH_OPEN, kernel)
    h_lines = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, h_kernel, iterations=2)
    v_lines = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, v_kernel, iterations=2)

    grid = cv2.add(h_lines, v_lines)

    contours, _ = cv2.findContours(grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > 100 and h > 60:  # filter tiny boxes
            boxes.append((x, y, w, h))

    # sort top-to-bottom, then left-to-right by row band
    boxes = sorted(boxes, key=lambda b: (b[1] // 80, b[0]))
    return boxes

def _ocr_cell(img_bgr: np.ndarray, box: Tuple[int,int,int,int]) -> str:
    x, y, w, h = box
    pad = 6
    x0, y0 = max(x + pad, 0), max(y + pad, 0)
    x1, y1 = min(x + w - pad, img_bgr.shape[1]), min(y + h - pad, img_bgr.shape[0])

    # Guard against invalid crop
    if x1 <= x0 or y1 <= y0:
        return ""

    crop = img_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return ""

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    txt = pytesseract.image_to_string(bw, config="--oem 3 --psm 6").strip()
    txt = _normalize_ocr_text(txt)
    txt = _strip_weekday_noise(txt)
    return txt

def _empty_per_day() -> Dict[str, Dict[str, List[str]]]:
    return {d: {m: [] for m in MEALS} for d in WEEKDAYS}

# -------- Text fallback to reconstruct per-day/meal when grid fails --------

_BREAKFAST_KEYS = ["waffle", "scrambled egg", "oatmeal", "french toast", "cereal"]

_SNACK_KEYWORDS = [
    "yogurt","graham","goldfish","raisin","carrot","ranch","cracker","granola",
    "peach","apple","peanut","butter","tortilla","bean","cucumber","pretzel",
    "string cheese","grape","rice cake","cream cheese","cookie","milk"
]

def _slice_by_weekday_blocks(text: str) -> Dict[str, str]:
    """
    Split the full OCR text into blocks following each weekday header.
    Returns {weekday: text_block_until_next_weekday}.
    """
    blocks: Dict[str, str] = {}
    norm = _normalize_ocr_text(text)
    idxs = []
    for m in re.finditer(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday)\b", norm, re.IGNORECASE):
        idxs.append((m.group(1).capitalize(), m.start()))
    idxs.sort(key=lambda x: x[1])
    for i, (day, start) in enumerate(idxs):
        end = idxs[i+1][1] if i+1 < len(idxs) else len(norm)
        blocks[day] = norm[start:end]
    return blocks

def _extract_breakfasts_from_blocks(blocks: Dict[str, str]) -> Dict[str, List[str]]:
    out = {d: [] for d in WEEKDAYS}
    for day, seg in blocks.items():
        foods = _extract_foods_from_text(seg)
        # keep breakfasty items only
        bf = []
        for f in foods:
            fl = f.lower()
            if any(k in fl for k in _BREAKFAST_KEYS) or f == "2% Milk" or f == "Fresh Fruit" or f == "Fruit":
                bf.append(f)
        # limit to a few items typical for breakfast cells
        out[day] = bf[:4]
    return out

def _extract_snack_pairs_by_order(text: str) -> Tuple[List[List[str]], List[List[str]]]:
    """
    Heuristic: after removing weekday headers and breakfast phrases, collect
    phrase blocks (split by blank lines), keep those that look like snack cells,
    and map first 5 to AM (Mon..Fri), next 5 to PM (Mon..Fri).
    """
    norm = _normalize_ocr_text(text)
    # Remove weekday headers to avoid leakage
    norm = WEEKDAY_RE.sub(" ", norm)
    # Remove obvious breakfast lines to avoid picking them as snacks
    for k in _BREAKFAST_KEYS:
        norm = re.sub(k, " ", norm, flags=re.IGNORECASE)
    norm = re.sub(r"\s{2,}", " ", norm)

    blocks = re.split(r"\n\s*\n", text)  # use original spacing for grouping
    candidates: List[List[str]] = []
    for bl in blocks:
        items = _extract_foods_from_text(bl)
        if not items:
            continue
        # require at least one snack-ish token
        if not any(any(kw in it.lower() for kw in _SNACK_KEYWORDS) for it in items):
            continue
        # keep small cells (1–3 items)
        if 1 <= len(items) <= 3:
            candidates.append(items)

    # Deduplicate consecutive identical cells
    deduped: List[List[str]] = []
    for c in candidates:
        if not deduped or c != deduped[-1]:
            deduped.append(c)

    am = deduped[:5]
    pm = deduped[5:10] if len(deduped) >= 10 else []
    return am, pm

def _fallback_per_day_from_fulltext(text: str) -> Dict[str, Dict[str, List[str]]]:
    per_day = _empty_per_day()

    blocks = _slice_by_weekday_blocks(text)
    breakfasts = _extract_breakfasts_from_blocks(blocks)
    for d in WEEKDAYS:
        per_day[d]["Breakfast"] = breakfasts.get(d, [])

    am, pm = _extract_snack_pairs_by_order(text)

    # Map AM/PM lists to weekdays in order
    for i, day in enumerate(WEEKDAYS):
        if i < len(am):
            per_day[day]["AM Snack"] = am[i]
        if i < len(pm):
            per_day[day]["PM Snack"] = pm[i]

    return per_day

# ------------------------------

def ocr_full_text(image_bytes: bytes) -> str:
    """Plain full-image OCR (no grid parsing) — used for non-menu circular images."""
    img_rgb = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return _normalize_ocr_text(pytesseract.image_to_string(img_rgb))


def parse_menu_image(image_bytes: bytes) -> ParsedMenu:
    """Parse a weekly menu image into per-day {meal → items} using grid cell OCR.
       If grid yields nothing, reconstruct per-day/meal from full OCR text.
    """
    # Load image
    img_rgb = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = np.array(img_rgb)[:, :, ::-1]  # RGB->BGR

    # Try grid-based parsing
    bin_img = _preprocess_for_grid(img)
    boxes = _find_cells(bin_img)

    rows: Dict[int, List[Tuple[int,int,int,int]]] = {}
    for b in boxes:
        band = b[1] // 180
        rows.setdefault(band, []).append(b)
    for k in rows:
        rows[k] = sorted(rows[k], key=lambda b: b[0])

    per_day = _empty_per_day()
    all_foods_accum: List[str] = []

    if rows:
        header_key = min(rows.keys())
        header_cells = rows[header_key]

        # map column index -> weekday
        col_to_day: Dict[int, str] = {}
        for ci, box in enumerate(header_cells):
            txt = _ocr_cell(img, box)
            for d in WEEKDAYS:
                if re.search(rf"\b{re.escape(d)}\b", txt, re.IGNORECASE):
                    col_to_day[ci] = d
                    break

        # body rows (expect meal label in first column)
        body_keys = [k for k in sorted(rows.keys()) if k != header_key]

        def infer_meal(label_text: str, idx: int) -> str:
            lt = label_text.lower()
            if "breakfast" in lt:
                return "Breakfast"
            if "am snack" in lt or ("a m" in lt and "snack" in lt):
                return "AM Snack"
            if "pm snack" in lt or ("p m" in lt and "snack" in lt):
                return "PM Snack"
            return MEALS[idx] if idx < len(MEALS) else f"Meal{idx+1}"

        for ri, rkey in enumerate(body_keys):
            row_cells = rows[rkey]
            if not row_cells:
                continue
            left_label = _ocr_cell(img, row_cells[0])
            meal = infer_meal(left_label, ri)

            for ci, box in enumerate(row_cells):
                if ci == 0:
                    continue
                day = col_to_day.get(ci) or col_to_day.get(ci-1) or col_to_day.get(ci+1)
                if not day:
                    continue
                cell_text = _ocr_cell(img, box)
                if not cell_text:
                    continue
                items = _extract_foods_from_text(cell_text)
                if not items:
                    continue
                per_day[day][meal].extend(items)
                for it in items:
                    if it not in all_foods_accum:
                        all_foods_accum.append(it)

    # Full-image OCR (for raw_text and robust fallback)
    raw_full = pytesseract.image_to_string(img_rgb)
    raw_full = _normalize_ocr_text(raw_full)

    # If grid yielded nothing useful, reconstruct from text
    has_any = any(per_day[d][m] for d in WEEKDAYS for m in MEALS)
    if not has_any:
        per_day = _fallback_per_day_from_fulltext(raw_full)

    # Populate all_foods if still empty
    if not all_foods_accum:
        all_foods_accum = _extract_foods_from_text(raw_full)

    return ParsedMenu(per_day=per_day, all_foods=all_foods_accum, raw_text=raw_full)

# ------------------------------
# Text Parser (backward compatible)
# ------------------------------

def _find_first_in_list(text_lower: str, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in text_lower:
            return c
    return None

def _find_all_in_list(text_lower: str, candidates: List[str]) -> List[str]:
    out = []
    for c in candidates:
        if c in text_lower:
            out.append(c)
    # dedup
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            uniq.append(x)
            seen.add(x)
    return uniq

def parse_text_to_tasks(text: str) -> ParsedNote:
    t = text.strip()
    t = _normalize_ocr_text(t)
    tl = t.lower()

    day = _find_first_in_list(tl, DAYS_LOWER)
    date_match = re.search(DATE_REGEX, t)
    time_match = re.search(TIME_REGEX, t)

    foods = _extract_foods_from_text(t)
    supplies = _find_all_in_list(tl, SUPPLY_HINTS)
    dress_code = _find_first_in_list(tl, [d.lower() for d in DRESS_HINTS])
    event = _find_first_in_list(tl, ["competition","picnic","field trip","presentation","exam","test","sports day","rehearsal","assembly","project"])

    # Optional: try per-day reconstruction in text mode too
    per_day = _fallback_per_day_from_fulltext(t)

    return ParsedNote(
        day=day.capitalize() if day else None,
        date=date_match.group(1) if date_match else None,
        time=time_match.group(1) if time_match else None,
        foods=foods,
        supplies=supplies,
        dress_code=dress_code,
        event=event,
        raw_text=t,
        per_day=per_day
    )

# ------------------------------
# Plan Builders
# ------------------------------

def _when_string(parsed: ParsedNote) -> Optional[str]:
    parts = [p for p in [parsed.day, parsed.date, parsed.time] if p]
    return " ".join(parts) if parts else None

def build_step(step_type: str, title: str, items: List[str] | None,
               when: Optional[str], place_query: Optional[str]):
    links = {}
    if place_query:
        links["maps_url"] = _maps_search_link(place_query)
        tail = " " + " ".join(items or []) if items else ""
        links["doordash_url"] = _doordash_search_link(place_query + tail)
    return {"type": step_type, "title": title, "items": items or [], "when": when, "links": links}

def build_plan_from_menu(menu: ParsedMenu) -> Dict:
    """Build steps using structured per_day menu first; fall back to all_foods."""
    steps: List[Dict] = []
    # Per-day steps
    has_any = False
    for day in WEEKDAYS:
        day_data = menu.per_day.get(day, {})
        for meal in MEALS:
            items = day_data.get(meal, [])
            if not items:
                continue
            has_any = True
            when = day
            steps.append(build_step("buy", f"Buy items for {day} – {meal}", items, when, "bakery near me"))
            steps.append(build_step("pack", f"Prepare/pack for {day} – {meal}", items, when, "grocery near me"))
    # Fallback: if nothing was found, at least list all foods
    if not has_any and menu.all_foods:
        steps.append(build_step("buy", "Buy lunch/snack items", menu.all_foods, None, "bakery near me"))
        steps.append(build_step("pack", "Prepare / pack items", menu.all_foods, None, "grocery near me"))
    steps.append(build_step("reminder", "Set pickup/drop plan", [], None, "daycare near me"))
    return {"steps": steps, "raw_text": menu.raw_text}

def build_supply_dress_event_steps(parsed: ParsedNote, when: Optional[str]) -> List[Dict]:
    """Build steps for supplies, dress code, and events — shared by build_plan()
    and any caller (e.g. the food-note branch in main.py) that builds its own
    food steps separately and still needs these non-food signals covered."""
    steps: List[Dict] = []

    if parsed.supplies:
        steps.append(build_step(
            "buy",
            f"Buy school supplies for {when or 'the day'}",
            parsed.supplies,
            when,
            place_query="stationery store near me"
        ))
        steps.append(build_step(
            "pack",
            f"Pack supplies: {', '.join(parsed.supplies)}",
            parsed.supplies,
            when,
            place_query=None
        ))

    if parsed.dress_code:
        steps.append(build_step(
            "prepare",
            f"Prepare dress code for {when or 'the day'}",
            [parsed.dress_code],
            when,
            place_query="uniform store near me"
        ))

    if parsed.event:
        steps.append(build_step(
            "reminder",
            f"Event: {parsed.event} scheduled",
            [],
            when,
            place_query=None
        ))

    return steps


def build_plan(parsed: ParsedNote) -> dict:
    steps: list[dict] = []
    when = _when_string(parsed)

    # ---------------- FOOD ----------------
    if parsed.foods:
        steps.append(build_step(
            "buy",
            f"Buy items for {when or 'the day'} – Lunch/Snack",
            parsed.foods,
            when,
            place_query="grocery store near me"
        ))
        steps.append(build_step(
            "pack",
            f"Prepare/pack for {when or 'the day'} – Lunch/Snack",
            parsed.foods,
            when,
            place_query="grocery store near me"
        ))

    # ---------------- SUPPLIES / DRESS CODE / EVENTS ----------------
    steps.extend(build_supply_dress_event_steps(parsed, when))

    # ---------------- DEFAULT FALLBACK ----------------
    if not steps:
        steps.append(build_step(
            "reminder",
            "Review the note and add tasks (no food/supplies detected)",
            [],
            when,
            place_query=None
        ))

    # Always add pickup/drop reminder
    steps.append(build_step(
        "reminder",
        "Set pickup/drop plan (consider carpool; check daycare/after-school if needed)",
        [],
        when,
        place_query="daycare near me"
    ))

    return {"steps": steps, "raw_text": parsed.raw_text}
