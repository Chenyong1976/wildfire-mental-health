"""Verify references in references.bib against Crossref and Semantic Scholar."""
import requests, json, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CROSSREF = "https://api.crossref.org/works/{doi}"
S2      = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,authors,year,externalIds,venue,publicationVenue"
NBER    = "https://api.semanticscholar.org/graph/v1/paper/search?query={title}&fields=title,authors,year,externalIds&limit=3"
HEADERS = {"User-Agent": "refcheck/1.0 (mailto:research@example.com)"}

REFS = [
    {"key": "jung2025",
     "doi": "10.1001/jamanetworkopen.2025.3326",
     "expected_authors": ["Jung", "Johnson", "Burke", "Heft-Neal"],
     "expected_year": 2025,
     "expected_article_no": "e253326"},
    {"key": "wettstein2024",
     "doi": "10.1001/jamanetworkopen.2023.56466",
     "expected_authors": ["Wettstein", "Vaidyanathan"],
     "expected_year": 2024,
     "expected_article_no": "e2356466"},
    {"key": "currie2025",
     "doi": None,
     "nber": "33912",
     "title": "Wildfire Smoke and Mental Health in Canada",
     "expected_authors": ["Currie", "Saberian"],
     "expected_year": 2025},
    {"key": "du2024",
     "doi": "10.3389/ijph.2024.1607128",
     "expected_authors": ["Du", "Liu", "Zhao", "Fang"],
     "expected_year": 2024,
     "expected_article_no": "1607128"},
    {"key": "ye2026",
     "doi": "10.1029/2025GH001534",
     "expected_authors": ["Ye", "Huang", "Onega"],
     "expected_year": 2026,
     "expected_article_no": "e2025GH001534"},
    {"key": "merdjanoff2026",
     "doi": "10.1088/1748-9326/ae6d16",
     "expected_authors": ["Merdjanoff", "Burrows", "Lynch"],
     "expected_year": 2026},
    {"key": "callaway2021",
     "doi": None,
     "title": "Difference-in-Differences with Multiple Time Periods",
     "expected_authors": ["Callaway", "Sant'Anna"],
     "expected_year": 2021},
    {"key": "imbens_kolesar2016",
     "doi": "10.1162/REST_a_00552",
     "expected_authors": ["Imbens", "Kolesar"],
     "expected_year": 2016},
    {"key": "greenberg2021",
     "doi": "10.1007/s40273-021-01019-4",
     "expected_authors": ["Greenberg", "Simes", "Berman", "Koenigsberg", "Kessler"],
     "expected_year": 2021},
]

def check_doi(doi):
    try:
        r = requests.get(CROSSREF.format(doi=doi), headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json().get("message", {})
    except Exception as e:
        print(f"  Crossref error: {e}")
    return None

def check_s2(doi):
    try:
        r = requests.get(S2.format(doi=doi), headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  S2 error: {e}")
    return None

def search_s2(title):
    try:
        r = requests.get(NBER.format(title=requests.utils.quote(title)),
                         headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", [])
    except Exception as e:
        print(f"  S2 search error: {e}")
    return []

def fmt_authors(items):
    if not items:
        return "?"
    names = []
    for a in items[:5]:
        if isinstance(a, dict):
            names.append(a.get("name", a.get("family", "?")))
        else:
            names.append(str(a))
    return ", ".join(names) + ("..." if len(items) > 5 else "")

print("=" * 70)
print("REFERENCE VERIFICATION REPORT")
print("Checking against Crossref + Semantic Scholar")
print("=" * 70)

for ref in REFS:
    key = ref["key"]
    print(f"\n[{key}]")

    cr_data = None
    s2_data = None

    if ref.get("doi"):
        cr_data = check_doi(ref["doi"])
        time.sleep(0.5)
        s2_data = check_s2(ref["doi"])
        time.sleep(0.5)

    # ---- Crossref result ----
    if cr_data:
        cr_title = " ".join(cr_data.get("title", ["?"]))
        cr_authors_raw = cr_data.get("author", [])
        cr_authors = [a.get("family", "?") for a in cr_authors_raw]
        cr_year = None
        for date_field in ["published", "published-print", "published-online"]:
            dp = cr_data.get(date_field, {}).get("date-parts", [[None]])
            if dp and dp[0] and dp[0][0]:
                cr_year = dp[0][0]
                break
        cr_pages = cr_data.get("page", "?")
        cr_journal = cr_data.get("container-title", ["?"])[0] if cr_data.get("container-title") else "?"

        print(f"  Crossref found:")
        print(f"    Title:   {cr_title[:80]}")
        print(f"    Authors: {', '.join(cr_authors[:6])}")
        print(f"    Year:    {cr_year}")
        print(f"    Journal: {cr_journal}")
        print(f"    Pages:   {cr_pages}")

        # check expected authors
        missing = [a for a in ref.get("expected_authors", [])
                   if not any(a.lower() in ca.lower() for ca in cr_authors)]
        if missing:
            print(f"  !! AUTHOR MISMATCH — expected but not found: {missing}")
            print(f"     Actual authors: {cr_authors}")
        else:
            print(f"  OK Authors match expected")

        if ref.get("expected_year") and cr_year != ref["expected_year"]:
            print(f"  !! YEAR MISMATCH — bib says {ref['expected_year']}, Crossref says {cr_year}")
        elif ref.get("expected_year"):
            print(f"  OK Year matches ({cr_year})")

        if ref.get("expected_article_no"):
            if ref["expected_article_no"] in str(cr_pages):
                print(f"  OK Article number {ref['expected_article_no']} found in pages field")
            else:
                print(f"  !! ARTICLE NO MISMATCH — bib says {ref['expected_article_no']}, Crossref pages: {cr_pages}")
    else:
        print(f"  Crossref: NOT FOUND (DOI may be wrong or paper not yet indexed)")

    # ---- Semantic Scholar result ----
    if s2_data:
        s2_title = s2_data.get("title", "?")
        s2_authors = [a.get("name", "?") for a in s2_data.get("authors", [])]
        s2_year = s2_data.get("year")
        print(f"  S2 title: {s2_title[:80]}")
        print(f"  S2 year:  {s2_year}")
    elif ref.get("doi"):
        print(f"  S2: not found via DOI")

    # ---- Title-search fallback for non-DOI refs ----
    if not ref.get("doi") and ref.get("title"):
        results = search_s2(ref["title"])
        time.sleep(0.5)
        if results:
            best = results[0]
            s2_title = best.get("title", "?")
            s2_authors_raw = best.get("authors", [])
            s2_authors = [a.get("name", "?") for a in s2_authors_raw]
            s2_year = best.get("year")
            print(f"  S2 search result:")
            print(f"    Title:   {s2_title[:80]}")
            print(f"    Authors: {', '.join(s2_authors[:6])}")
            print(f"    Year:    {s2_year}")
            missing = [a for a in ref.get("expected_authors", [])
                       if not any(a.lower() in sa.lower() for sa in s2_authors)]
            if missing:
                print(f"  !! AUTHOR MISMATCH: {missing}")
            else:
                print(f"  OK Authors match")
        else:
            print(f"  S2: no results found for title search")

print("\n" + "=" * 70)
print("Done.")
