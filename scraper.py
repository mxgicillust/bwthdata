import requests
import json
import os
import time
from collections import defaultdict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_FILE = "data.json"
SYNOPSIS_CACHE_FILE = "synopsis_cache.json"

REQUEST_DELAY = 0.5      # seconds between per-book synopsis requests
MAX_RETRIES = 3          # attempts before giving up on a single book
CHECKPOINT_EVERY = 50    # flush cache to disk every N fetches

# ---------------------------------------------------------------------------
# Title / series helpers  (unchanged from original)
# ---------------------------------------------------------------------------

def clean_title_kana(title: str) -> str:
    cleaned = title.replace("(ฉบับนิยาย)", "")
    cleaned = cleaned.replace("(นิยาย)", "")
    cleaned = cleaned.replace("เล่ม", "")
    cleaned = cleaned.replace("ํา", "ำ")
    cleaned = cleaned.lower()
    cleaned = "".join(cleaned.split())
    return cleaned


def replace_prefix(text: str, old_prefix: str, new_prefix: str) -> str:
    if text.startswith(old_prefix):
        return new_prefix + text[len(old_prefix):]
    return text


def normalize_series_name(name: str) -> str:
    return name.replace("(ฉบับนิยาย)", "").replace("(นิยาย)", "").strip()


locked_names: dict[str, str] = {
    "ไซเลนต์วิตช์ ความลับของแม่มดแห่งความเงียบ": "ไซเลนต์วิตช์",
    "ผู้ดูแลเด็กสาว, ผมกลายเป็นผู้ดูแลแบบลับ ๆ ของคุณหนู (ที่ไม่มีความสามารถในการดำรงชีพ) ที่แสนเพียบพร้อมของโรงเรียนมัธยมอันทรงเกียรติที่เต็มไปด้วยดอกฟ้า": "ผู้ดูแลเด็กสาว",
    "ผู้ดูแลเด็กสาว (ฉบับนิยาย)": "ผู้ดูแลเด็กสาว",
    "นี่ เรามาคบกันมั้ย? เมื่อเพื่อนสมัยเด็กคนสวยขอมา ชีวิตแฟนกำมะลอของผมจึงเริ่มขึ้น (นิยาย) ": "นี่ เรามาคบกันมั้ย?",
    "บันทึกเรื่องราวจักรวรรดิเทียร์มูน -จุดพลิกผันชะตากรรมของเจ้าหญิงเริ่มจากบนกิโยติน- (ฉบับนิยาย)": "บันทึกเรื่องราวจักรวรรดิเทียร์มูน",
    "นักดาบแรงก์ S ถูกปาร์ตีทิ้งไว้ในวงกตสุดโหดจนหลงไปยังส่วนลึกสุดที่ไม่มีใครรู้จัก ～ จากเซนส์ฉันทางนี้น่าจะเป็นทางออก ～": "นักดาบแรงก์ S ถูกปาร์ตีทิ้งไว้ในวงกตสุดโหดจนหลงไปยังส่วนลึกสุดที่ไม่มีใครรู้จัก",
    "สัมพันธ์ลับสัปดาห์ละครั้ง ～ช่วงเวลาห้าพันเยนของสองเรา～": "สัมพันธ์ลับสัปดาห์ละครั้ง",
}

# ---------------------------------------------------------------------------
# Synopsis cache  — persisted in synopsis_cache.json and committed to the repo
#
# Schema: { "<uuid>": "<synopsis text or null>" }
#
# A UUID present in the cache (even with a null value) means the product API
# was called successfully for that book; it will be skipped on future runs.
# A UUID absent from the cache means the fetch either hasn't happened yet OR
# failed — both cases are retried next run.
# ---------------------------------------------------------------------------

def load_synopsis_cache() -> dict:
    if os.path.exists(SYNOPSIS_CACHE_FILE):
        with open(SYNOPSIS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_synopsis_cache(cache: dict) -> None:
    with open(SYNOPSIS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)


# ---------------------------------------------------------------------------
# Per-book synopsis fetch  (with exponential back-off)
# ---------------------------------------------------------------------------

def fetch_synopsis(uuid: str, session: requests.Session) -> tuple[bool, str | None]:
    """
    Call /api/products/{uuid}/ and return (success, synopsis).

    Returns (False, None) on permanent or exhausted-retry failures —
    the caller must NOT cache this so the book is retried next run.
    """
    url = f"https://bookwalker.in.th/api/products/{uuid}/"

    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(url, timeout=30)

            if response.status_code == 200:
                synopsis = (
                    response.json()
                    .get("data", {})
                    .get("productExplanationDetails")
                )
                return True, synopsis

            if response.status_code == 429:
                # Respect rate-limit: exponential back-off 60 → 120 → 240 s
                wait = 60 * (2 ** attempt)
                print(f"  [429] rate-limited on {uuid}, backing off {wait}s …")
                time.sleep(wait)

            elif response.status_code in (502, 503, 504):
                wait = 15 * (2 ** attempt)
                print(f"  [{response.status_code}] server error on {uuid}, retrying in {wait}s …")
                time.sleep(wait)

            else:
                # 404, 403, etc. — no point retrying
                print(f"  [{response.status_code}] permanent error for {uuid}, skipping")
                return False, None

        except requests.RequestException as e:
            wait = 10 * (2 ** attempt)
            print(f"  [network] {uuid}: {e} — retrying in {wait}s …")
            time.sleep(wait)

    print(f"  Gave up on {uuid} after {MAX_RETRIES} attempts")
    return False, None


# ---------------------------------------------------------------------------
# Main fetch
# ---------------------------------------------------------------------------

def fetch() -> list:
    # ------------------------------------------------------------------
    # Step 1 — fetch the full book list  (single request, cheap)
    # ------------------------------------------------------------------
    list_url = (
        "https://bookwalker.in.th/api/categories/3/"
        "?p=1&p_size=10000&sort_by=release_date"
    )
    list_resp = requests.get(list_url, timeout=60)
    if list_resp.status_code != 200:
        print(f"Failed to fetch book list: {list_resp.status_code}")
        return []

    raw_list = list_resp.json().get("data", [])

    # ------------------------------------------------------------------
    # Step 2 — parse / group books  (no synopsis yet)
    # ------------------------------------------------------------------
    skip_prefixes = ("[Short Story Set]", "[ยกชุด]")

    grouped: dict[str, dict] = defaultdict(lambda: {
        "seriesName": "",
        "seriesId": "",
        "publisherId": "",
        "publisherName": "",
        "books": [],
    })

    # Flat list keeps insertion order and lets us attach synopses later
    all_entries: list[dict] = []  # [{"series_id": …, "book": {…}}, …]

    for item in raw_list:
        product_name = item.get("name", "")
        if product_name.startswith(skip_prefixes):
            continue

        series_id = item.get("seriesId")
        if not series_id:
            continue

        original_series_name = item.get("seriesName", "")
        normalized_name = normalize_series_name(original_series_name)
        locked_series_name = locked_names.get(normalized_name, normalized_name)

        # Update series metadata (last-write wins — same series, same data)
        grouped[series_id]["seriesName"] = locked_series_name
        grouped[series_id]["seriesId"] = series_id
        grouped[series_id]["publisherId"] = item.get("publisherId")
        grouped[series_id]["publisherName"] = item.get("publisherName")

        title_kana = replace_prefix(
            clean_title_kana(product_name),
            "".join(normalize_series_name(original_series_name).split()),
            "".join(locked_series_name.split()),
        )

        book_entry = {
            "title": product_name,
            "titleKana": title_kana,
            "uuid": item.get("uuid"),
            "productId": item.get("productId"),
            "synopsis": None,          # filled in step 4
            "coverFileName": item.get("coverFileName"),
            "purchasedCount": item.get("purchasedCount"),  # always fresh from list API
        }
        all_entries.append({"series_id": series_id, "book": book_entry})

    # ------------------------------------------------------------------
    # Step 3 — load cache, find only the books that need a synopsis call
    # ------------------------------------------------------------------
    synopsis_cache = load_synopsis_cache()

    new_entries = [
        e for e in all_entries
        if e["book"]["uuid"] and e["book"]["uuid"] not in synopsis_cache
    ]

    print(
        f"Books in list: {len(all_entries)} | "
        f"Already cached: {len(synopsis_cache)} | "
        f"New (need fetch): {len(new_entries)}"
    )

    # ------------------------------------------------------------------
    # Step 4 — fetch synopses only for new books
    # ------------------------------------------------------------------
    if new_entries:
        with requests.Session() as session:
            session.headers.update({"User-Agent": "Mozilla/5.0 (compatible)"})

            for i, entry in enumerate(new_entries):
                uuid = entry["book"]["uuid"]
                success, synopsis = fetch_synopsis(uuid, session)

                if success:
                    # Cache successful fetches (even if synopsis is None/empty)
                    synopsis_cache[uuid] = synopsis
                # On failure: do NOT cache — the book will be retried next run

                if (i + 1) % CHECKPOINT_EVERY == 0:
                    print(f"  Checkpoint: {i + 1}/{len(new_entries)} — saving cache …")
                    save_synopsis_cache(synopsis_cache)

                time.sleep(REQUEST_DELAY)

        save_synopsis_cache(synopsis_cache)
        print(f"Synopsis fetch complete. {len(new_entries)} books processed.")

    # ------------------------------------------------------------------
    # Step 5 — attach synopses and build the final output
    # ------------------------------------------------------------------
    for entry in all_entries:
        book = entry["book"]
        book["synopsis"] = synopsis_cache.get(book["uuid"])
        grouped[entry["series_id"]]["books"].append(book)

    result = list(grouped.values())

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"Wrote {len(result)} series → {DATA_FILE}")
    return result


if __name__ == "__main__":
    fetch()
