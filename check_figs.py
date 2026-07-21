import zipfile, re

with zipfile.ZipFile('paper_combined.docx') as z:
    xml = z.read('word/document.xml').decode('utf-8')
    # Find the drawing/picture elements
    # Look for cx/cy (width/height in EMUs)
    extents = re.findall('<wp:extent cx="([^"]+)" cy="([^"]+)"', xml)
    print('Image extents (cx, cy in EMUs):')
    for cx, cy in extents:
        w_in = int(cx) / 914400
        h_in = int(cy) / 914400
        print(f'  {cx} x {cy} EMU = {w_in:.2f}" x {h_in:.2f}"')

with zipfile.ZipFile('figures.docx') as z:
    xml = z.read('word/document.xml').decode('utf-8')
    extents = re.findall('<wp:extent cx="([^"]+)" cy="([^"]+)"', xml)
    print('figures.docx image extents:')
    for cx, cy in extents:
        w_in = int(cx) / 914400
        h_in = int(cy) / 914400
        print(f'  {cx} x {cy} EMU = {w_in:.2f}" x {h_in:.2f}"')
