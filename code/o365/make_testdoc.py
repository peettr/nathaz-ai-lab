#!/usr/bin/env python3
"""造一份图文混排测试 docx：图片、表格、页眉页脚、两栏分节、文本框、编号列表、跨 run 的格式。用法：make_testdoc.py <out.docx>"""
import sys, io, copy
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import parse_xml
from PIL import Image, ImageDraw

out = sys.argv[1]
d = Document()
sec = d.sections[0]
sec.header.paragraphs[0].text = "Test Proposal — Header (L26.25 OOXML test)"
sec.footer.paragraphs[0].text = "Footer: confidential draft, page footer text"
d.add_heading("Wind Engineering Proposal: OOXML Revision Test", 0)
p = d.add_paragraph("This proposal describe a new method for ")
r = p.add_run("nonstationary wind loads"); r.bold = True
p.add_run(" on tall building, and it compare the results with wind tunnel data.")
d.add_paragraph("The key objectives are listed below.")
for t in ["Develop a time-frequency load model.", "Validate the model againts field measurements.", "Release open source code for practitioners."]:
    d.add_paragraph(t, style="List Number")
img = Image.new("RGB", (600, 300), "white"); g = ImageDraw.Draw(img)
g.rectangle([20, 20, 580, 280], outline="navy", width=4); g.line([40, 260, 200, 120, 360, 180, 560, 40], fill="red", width=5)
g.text((240, 270), "Figure 1 test image", fill="black")
bio = io.BytesIO(); img.save(bio, "PNG"); bio.seek(0)
d.add_picture(bio, width=Inches(4.5))
cap = d.add_paragraph("Figure 1. Peak response versus reduced velocity in the wind tunnel."); cap.runs[0].italic = True
tb = d.add_table(rows=3, cols=3); tb.style = "Light Grid Accent 1"
for i, row in enumerate([["Case", "Height (m)", "Peak factor"], ["A", "120", "3.5"], ["B", "300", "3.8 (estimated)"]]):
    for j, v in enumerate(row):
        tb.cell(i, j).text = v
d.add_paragraph("Table 1 summarise the two test cases used in this study.")
# 两栏分节
ns = d.add_section(WD_SECTION.CONTINUOUS)
cols = ns._sectPr.xpath("./w:cols")
c = cols[0] if cols else ns._sectPr.makeelement(qn("w:cols"), {})
c.set(qn("w:num"), "2"); c.set(qn("w:space"), "720")
if not cols: ns._sectPr.append(c)
for k in range(3):
    d.add_paragraph(f"Two-column paragraph {k+1}: the wind field are simulated with a large eddy simulation and the results is compared against the boundary layer wind tunnel measurements at several heights.")
# 文本框（VML 旧式文本框，Word 与 LibreOffice 都认）
tbx = parse_xml('<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:v="urn:schemas-microsoft-com:vml">'
               '<w:r><w:pict><v:shape id="tb1" type="#_x0000_t202" style="width:300pt;height:60pt" strokecolor="#1f4e79"><v:textbox><w:txbxContent>'
               '<w:p><w:r><w:t>Text box: the budget request are 300 SU per year.</w:t></w:r></w:p></w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>')
d.element.body.insert(len(d.element.body) - 1, tbx)
d.add_section(WD_SECTION.CONTINUOUS)
d.add_paragraph("Closing paragraph in one column. We thanks the reviewers for there comments.")
d.save(out)
print("ok", out)
