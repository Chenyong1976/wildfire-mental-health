"""Diagnostic: dump drawing XML and sectPr positions from paper_combined.docx."""
import zipfile, re, sys

path = r"C:\Users\chenyon\Research Paper 2026(1)\paper_combined.docx"

with zipfile.ZipFile(path) as z:
    xml = z.read("word/document.xml").decode("utf-8")

# 1. Show every <w:drawing ...> block (truncated)
print("=== DRAWING ELEMENTS ===")
for i, m in enumerate(re.finditer(r"<w:drawing>.*?</w:drawing>", xml, re.DOTALL)):
    block = m.group()
    print(f"\n-- Drawing {i+1} --")
    # Show extent, docPr id, blip embed ref
    ext = re.search(r'<wp:extent cx="([^"]+)" cy="([^"]+)"', block)
    docpr = re.search(r'<wp:docPr id="([^"]+)" name="([^"]+)"', block)
    blip = re.search(r'r:embed="([^"]+)"', block)
    if ext:
        cx, cy = int(ext.group(1)), int(ext.group(2))
        print(f"  extent: {cx/914400:.2f}\" x {cy/914400:.2f}\"")
    if docpr:
        print(f"  docPr id={docpr.group(1)} name={docpr.group(2)}")
    if blip:
        print(f"  blip embed: {blip.group(1)}")

# 2. Count sectPr elements and show their type
print("\n=== SECTION PROPERTIES (w:sectPr) ===")
for i, m in enumerate(re.finditer(r"<w:sectPr[ >].*?</w:sectPr>", xml, re.DOTALL)):
    block = m.group()
    pgSz = re.search(r'<w:pgSz[^/]*/>', block)
    pgMar = re.search(r'<w:pgMar[^/]*/>', block)
    secType = re.search(r'<w:type w:val="([^"]+)"', block)
    print(f"\n-- sectPr {i+1} --")
    if secType:
        print(f"  type: {secType.group(1)}")
    else:
        print("  type: (not specified = nextPage)")
    if pgSz:
        w_attr = re.search(r'w:w="([^"]+)"', pgSz.group())
        h_attr = re.search(r'w:h="([^"]+)"', pgSz.group())
        if w_attr and h_attr:
            print(f"  page: {int(w_attr.group(1))/1440:.2f}\" x {int(h_attr.group(1))/1440:.2f}\"")
    if pgMar:
        top = re.search(r'w:top="([^"]+)"', pgMar.group())
        bot = re.search(r'w:bottom="([^"]+)"', pgMar.group())
        lft = re.search(r'w:left="([^"]+)"', pgMar.group())
        rgt = re.search(r'w:right="([^"]+)"', pgMar.group())
        if top and bot:
            print(f"  margins top={int(top.group(1))/1440:.2f}\" bot={int(bot.group(1))/1440:.2f}\"", end="")
        if lft and rgt:
            print(f" left={int(lft.group(1))/1440:.2f}\" right={int(rgt.group(1))/1440:.2f}\"")
        else:
            print()

# 3. Show pPr of paragraphs containing drawings
print("\n=== PARAGRAPH PROPS AROUND EACH DRAWING ===")
# Find each <w:p>...</w:p> that contains a drawing
for i, m in enumerate(re.finditer(r"<w:p[ >].*?</w:p>", xml, re.DOTALL)):
    pblock = m.group()
    if "<w:drawing>" not in pblock:
        continue
    print(f"\n-- Image paragraph {i+1} --")
    pPr = re.search(r"<w:pPr>(.*?)</w:pPr>", pblock, re.DOTALL)
    if pPr:
        print("  pPr:", pPr.group(1).replace("\n","").replace("  ","")[:300])
    else:
        print("  pPr: (none)")
