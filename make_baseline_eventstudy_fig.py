"""
Combine 2015_eventstudy_ihs_suicide_rate.png and 2015_eventstudy_ihs_overdose_rate.png
into a side-by-side composite for Figure 3 (baseline event study).
Crops the R-generated title block from the top of each source image.
"""
from PIL import Image, ImageDraw, ImageFont
import os

BASE = r"C:\Users\chenyon\Research Paper 2026(1)"

suicide_path  = os.path.join(BASE, "figures", "2015_eventstudy_ihs_suicide_rate.png")
overdose_path = os.path.join(BASE, "figures", "2015_eventstudy_ihs_overdose_rate.png")
out_path      = os.path.join(BASE, "fig_baseline_eventstudy.png")

img_s = Image.open(suicide_path).convert("RGB")
img_o = Image.open(overdose_path).convert("RGB")

# Source images are 1800x1080 at ~180 DPI.
# The ggplot title block occupies the top ~130px; crop it off.
CROP_TOP = 130
w_src, h_src = img_s.size          # 1800, 1080
img_s = img_s.crop((0, CROP_TOP, w_src, h_src))   # → 1800×950
img_o = img_o.crop((0, CROP_TOP, w_src, h_src))

# Resize each cropped panel to target width, preserving aspect ratio
panel_w = 1300
panel_h = round(panel_w * img_s.size[1] / img_s.size[0])   # ≈ 686
img_s = img_s.resize((panel_w, panel_h), Image.LANCZOS)
img_o = img_o.resize((panel_w, panel_h), Image.LANCZOS)

# Composite: two panels side by side with a narrow white gap
gap = 24
composite_w = panel_w * 2 + gap
composite_h = panel_h
composite = Image.new("RGB", (composite_w, composite_h), (255, 255, 255))
composite.paste(img_s, (0, 0))
composite.paste(img_o, (panel_w + gap, 0))

composite.save(out_path, dpi=(150, 150))

size_kb = os.path.getsize(out_path) / 1024
print(f"Saved: {out_path}")
print(f"  Source after crop: {img_s.size[0]}x{img_s.size[1]} per panel")
print(f"  Composite: {composite.size[0]}x{composite.size[1]} px at 150 DPI")
print(f"  Natural: {composite.size[0]/150:.2f}\" x {composite.size[1]/150:.2f}\"")
print(f"  At 6.5\" width in Word: height = {6.5 * composite.size[1] / composite.size[0]:.2f}\"")
print(f"  File: {size_kb:.1f} KB")
