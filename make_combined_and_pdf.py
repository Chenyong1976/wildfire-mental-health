"""
Single Word COM session:
  - Open master, insert text sections, save -> paper_combined.docx
  - Continue in the same document: append figures section
  - Save .docx, export PDF, quit
"""
import os, time
import win32com.client as win32

BASE = r"C:\Users\chenyon\Research Paper 2026(1)"

TEXT_SECTIONS = [
    "introduction.docx",
    "section_data.docx",
    "section_empirical.docx",
    "section_results.docx",
    "section_robustness.docx",
    "section_conclusion.docx",
    "references.docx",
]

FIG1 = os.path.join(BASE, "fig_common_support.png")
FIG2 = os.path.join(BASE, "fig_depression_coefplot.png")
FIG3 = os.path.join(BASE, "fig_baseline_eventstudy.png")
FIG4 = os.path.join(BASE, "fig_eventstudy.png")
FIG5 = os.path.join(BASE, "fig_rucc.png")

OUT_DOCX = os.path.join(BASE, "paper_combined.docx")
OUT_PDF  = os.path.join(BASE, "paper_combined.pdf")

word = win32.Dispatch("Word.Application")
word.Visible = False

try:
    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 1: Merge text sections
    # ─────────────────────────────────────────────────────────────────────────
    print("Phase 1: Merging text sections...")
    master_path = os.path.join(BASE, TEXT_SECTIONS[0])
    wdoc = word.Documents.Open(master_path, ReadOnly=False)
    time.sleep(0.5)

    for sec in TEXT_SECTIONS[1:]:
        path = os.path.join(BASE, sec)
        print(f"  Inserting {sec}...")
        sel = word.Selection
        sel.EndKey(Unit=6)       # wdStory
        sel.InsertBreak(Type=7)  # wdPageBreak
        sel.EndKey(Unit=6)
        sel.InsertFile(FileName=path, Range='',
                       ConfirmConversions=False, Link=False, Attachment=False)
        time.sleep(0.3)

    if os.path.exists(OUT_DOCX):
        os.remove(OUT_DOCX)
    wdoc.SaveAs2(OUT_DOCX, FileFormat=16)   # wdFormatDocx — document stays open
    print(f"  Text sections saved: {OUT_DOCX}")

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 2: Append figures — same document, same Word session
    # ─────────────────────────────────────────────────────────────────────────
    print("Phase 2: Appending figures...")

    sel = word.Selection

    # wdAlignParagraphCenter=1, wdAlignParagraphLeft=0
    # wdLineSpaceExactly=4

    def fmt_text(center=False, bold=False, font_size=12,
                 sp_before=0, sp_after=0, line_pts=24):
        sel.ParagraphFormat.Alignment      = 1 if center else 0
        sel.ParagraphFormat.SpaceBefore    = sp_before
        sel.ParagraphFormat.SpaceAfter     = sp_after
        sel.ParagraphFormat.LineSpacingRule = 4   # wdLineSpaceExactly
        sel.ParagraphFormat.LineSpacing    = line_pts
        sel.Font.Name   = "Times New Roman"
        sel.Font.Size   = font_size
        sel.Font.Bold   = bold
        sel.Font.Italic = False

    def fmt_image(sp_after=6):
        # wdLineSpaceSingle = 0
        pf = sel.ParagraphFormat
        pf.LineSpacingRule = 0    # wdLineSpaceSingle — never Exactly for images
        pf.LineSpacing     = 12
        pf.SpaceBefore     = 0
        pf.SpaceAfter      = sp_after
        pf.KeepWithNext    = False
        pf.KeepTogether    = False
        pf.Alignment       = 1    # center
        sel.Font.Name = "Times New Roman"
        sel.Font.Size = 12

    # Apply wdLineSpaceSingle to the Normal style so no inherited Exactly
    # spacing can leak into image paragraphs through the style hierarchy.
    norm = wdoc.Styles("Normal")
    norm.ParagraphFormat.LineSpacingRule = 0   # wdLineSpaceSingle
    norm.ParagraphFormat.LineSpacing     = 12

    sel.EndKey(Unit=6)   # wdStory — go to end

    # ── "Figures" heading on a new page ──────────────────────────────────────
    sel.InsertBreak(Type=7)
    sel.EndKey(Unit=6)

    fmt_text(center=True, bold=True, font_size=12, sp_before=0, sp_after=12, line_pts=24)
    sel.TypeText("Figures")
    sel.TypeParagraph()

    sel.TypeParagraph()   # empty line before Figure 1

    # ── Figure 1: Common support ─────────────────────────────────────────────
    print("  Inserting Figure 1...")
    fmt_image(sp_after=6)
    shape1 = sel.InlineShapes.AddPicture(
        FileName=FIG1, LinkToFile=False, SaveWithDocument=True)
    shape1.Width = 6.0 * 72
    print(f"    {shape1.Width/72:.2f}\" x {shape1.Height/72:.2f}\"")
    sel.TypeParagraph()

    fmt_text(bold=True, font_size=11, sp_before=0, sp_after=4, line_pts=18)
    sel.TypeText(
        "Figure 1. Common Support: Covariate Overlap Between Treated and Matched "
        "Controls (T1, >=1,000 acres)")
    sel.Font.Bold = False
    sel.TypeParagraph()

    fmt_text(font_size=10, sp_before=0, sp_after=10, line_pts=16)
    sel.TypeText(
        "Notes: Treated counties experienced a qualifying 2015 wildfire "
        "(T1, >= 1,000 acres). Controls matched within WHP quintiles via "
        "Mahalanobis distance. Top-left: WHP national rank distributions; vertical "
        "dashed lines mark quintile boundaries (0.2, 0.4, 0.6, 0.8). Top-right: "
        "paired WHP ranks colored by quintile; 45-degree line = perfect match. "
        "Bottom panels: RUCC and pre-treatment suicide rate distributions. "
        "Near-identical distributions confirm common support across all matching "
        "dimensions.")
    sel.TypeParagraph()

    # ── Figure 2: Depression coefficient plot — new page ─────────────────────
    print("  Inserting Figure 2...")
    sel.InsertBreak(Type=7)
    sel.EndKey(Unit=6)

    sel.TypeParagraph()   # empty line before Figure 2

    fmt_image(sp_after=6)
    shape2 = sel.InlineShapes.AddPicture(
        FileName=FIG2, LinkToFile=False, SaveWithDocument=True)
    shape2.Width = 6.4 * 72
    print(f"    {shape2.Width/72:.2f}\" x {shape2.Height/72:.2f}\"")
    sel.TypeParagraph()

    fmt_text(bold=True, font_size=11, sp_before=0, sp_after=4, line_pts=18)
    sel.TypeText(
        "Figure 2. Treatment Effects on Depression Prevalence and Poor Mental "
        "Health Days: Cross-Sectional DiD by Fire-Size Threshold (2019)")
    sel.Font.Bold = False
    sel.TypeParagraph()

    fmt_text(font_size=10, sp_before=0, sp_after=10, line_pts=16)
    sel.TypeText(
        "Notes: Coefficient plot summarizing Table 2. Each estimate shows the "
        "matched DiD coefficient with 95% confidence interval. Panel A: CDC PLACES "
        "depression prevalence (%). Panel B: CDC PLACES poor mental health days (%). "
        "Filled circles = binary treatment indicator; open diamonds = log(1 + "
        "PctBurned) dose-response among T1 treated counties. T1 (>= 1,000 ac) blue, "
        "T2 (>= 5,000 ac) gray, T3 (>= 25,000 ac) light gray. "
        "Dose-response shown in red. *** p < 0.01, ** p < 0.05, * p < 0.10. "
        "Heteroskedasticity-robust SEs.")
    sel.TypeParagraph()

    # ── Figure 3: Baseline event study — new page ────────────────────────────
    print("  Inserting Figure 3...")
    sel.InsertBreak(Type=7)
    sel.EndKey(Unit=6)

    sel.TypeParagraph()   # empty line before Figure 3

    fmt_image(sp_after=6)
    shape3 = sel.InlineShapes.AddPicture(
        FileName=FIG3, LinkToFile=False, SaveWithDocument=True)
    shape3.Width = 6.5 * 72
    print(f"    {shape3.Width/72:.2f}\" x {shape3.Height/72:.2f}\"")
    sel.TypeParagraph()

    fmt_text(bold=True, font_size=11, sp_before=0, sp_after=4, line_pts=18)
    sel.TypeText(
        "Figure 3. Baseline Event-Study Coefficients: TWFE Estimates of Wildfire "
        "Effects on Suicide and Overdose Mortality (2015 Cohort)")
    sel.Font.Bold = False
    sel.TypeParagraph()

    fmt_text(font_size=10, sp_before=0, sp_after=10, line_pts=16)
    sel.TypeText(
        "Notes: Left panel = IHS suicide rate; right panel = IHS overdose rate. "
        "Each panel overlays TWFE event-study coefficients (filled circles) and "
        "95% confidence intervals for all three fire-size thresholds: T1 (>=1,000 "
        "acres, red), T2 (>=5,000 acres, blue), T3 (>=25,000 acres, green). "
        "Reference year k = -1 (2014) normalized to zero (hollow circle). "
        "Western U.S. counties, pop. >= 10,000. SEs clustered by county.")
    sel.TypeParagraph()

    # ── Figure 4: Threshold event study — new page ───────────────────────────
    print("  Inserting Figure 4...")
    sel.InsertBreak(Type=7)
    sel.EndKey(Unit=6)

    sel.TypeParagraph()   # empty line before Figure 4

    fmt_image(sp_after=6)
    shape4 = sel.InlineShapes.AddPicture(
        FileName=FIG4, LinkToFile=False, SaveWithDocument=True)
    shape4.Width = 6.2 * 72
    print(f"    {shape4.Width/72:.2f}\" x {shape4.Height/72:.2f}\"")
    sel.TypeParagraph()

    fmt_text(bold=True, font_size=11, sp_before=0, sp_after=4, line_pts=18)
    sel.TypeText(
        "Figure 4. Event-Study Coefficients: Wildfire Effects on Suicide and "
        "Overdose Mortality, by Fire-Size Threshold")
    sel.Font.Bold = False
    sel.TypeParagraph()

    fmt_text(font_size=10, sp_before=0, sp_after=10, line_pts=16)
    sel.TypeText(
        "Notes: Each panel plots TWFE event-study coefficients (filled circles) and "
        "95% confidence intervals from equation (2), with reference year k = -1 "
        "(2014) normalized to zero (hollow circle). Outcome is IHS-transformed "
        "mortality rate per 100,000. Shaded region = pre-treatment window. Dashed "
        "vertical line separates pre- from post-treatment. SEs clustered by county.")
    sel.TypeParagraph()

    # ── Figure 5: Rurality heterogeneity — new page ──────────────────────────
    print("  Inserting Figure 5...")
    sel.InsertBreak(Type=7)
    sel.EndKey(Unit=6)

    sel.TypeParagraph()   # empty line before Figure 5

    fmt_image(sp_after=6)
    shape5 = sel.InlineShapes.AddPicture(
        FileName=FIG5, LinkToFile=False, SaveWithDocument=True)
    shape5.Width = 5.8 * 72
    print(f"    {shape5.Width/72:.2f}\" x {shape5.Height/72:.2f}\"")
    sel.TypeParagraph()

    fmt_text(bold=True, font_size=11, sp_before=0, sp_after=4, line_pts=18)
    sel.TypeText(
        "Figure 5. Rurality Heterogeneity: Event-Study Coefficients by Metro / "
        "Non-Metro Classification (T1, >=1,000 acres)")
    sel.Font.Bold = False
    sel.TypeParagraph()

    fmt_text(font_size=10, sp_before=0, sp_after=10, line_pts=16)
    sel.TypeText(
        "Notes: T1 threshold (>= 1,000 acres). Each panel plots TWFE event-study "
        "coefficients from equation (2) estimated separately within metropolitan "
        "(RUCC 1-3) and non-metropolitan (RUCC 4-9) county subgroups. "
        "Non-metropolitan CI bars clipped at +/-2.5 IHS units for readability; "
        "true CIs are wider for k = -2 to k = +3. * p < 0.05 at k = +4 "
        "(non-metropolitan suicide). SEs clustered by county.")
    sel.TypeParagraph()

    # ── Save docx ────────────────────────────────────────────────────────────
    wdoc.Save()
    print(f"  Word document saved: {OUT_DOCX}")

    # ── Export PDF ───────────────────────────────────────────────────────────
    wdoc.ExportAsFixedFormat(
        OutputFileName=OUT_PDF,
        ExportFormat=17,
        OpenAfterExport=False,
        OptimizeFor=0,
        Range=0,
        IncludeDocProps=True,
        KeepIRM=True,
        CreateBookmarks=0,
        DocStructureTags=True,
        BitmapMissingFonts=True,
        UseISO19005_1=False,
    )
    print(f"  PDF exported: {OUT_PDF}")

    wdoc.Close(SaveChanges=False)

finally:
    word.Quit()

size_mb = os.path.getsize(OUT_PDF) / (1024 * 1024)
print(f"\nFinal PDF size: {size_mb:.2f} MB")
print("Done.")
