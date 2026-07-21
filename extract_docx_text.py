from docx import Document
import re

doc = Document(r"C:\Users\chenyon\Research Paper 2026(1)\paper_combined.docx")
lines = []
for para in doc.paragraphs:
    t = para.text.strip()
    if t:
        lines.append(t)

with open(r"C:\Users\chenyon\Research Paper 2026(1)\docx_extracted.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Done. Lines:", len(lines))
