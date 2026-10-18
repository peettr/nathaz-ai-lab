"""Append a correction/source band to r5 figures without altering originals."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
SOURCES = [
    'Sources: CRASAR-U-DROIDs (Manzini et al., 2024, arXiv:2407.17673; CC BY 4.0);',
    'H2 reconstruction (Lab H); NHC best track + potential-inundation map; USGS 3DEP.',
]
CAUTIONS = [
    'CORRECTION: Ian Harlem Heights (1.02-1.05 RMW) and Idalia Jena gusts are near-core /',
    'not observationally validated at the buildings. Near-core bin: UNVALIDATED; exclude',
    'from primary wind-damage gradient inference. Existing plotted counts remain archival.',
    'After conservative water-risk exclusion: 0 eligible buildings; no primary gradient.',
]
for name in ('r5_damage_probability_exploratory', 'r5_damage_probability_rmw_supplement'):
    source = ROOT / (name + '.png')
    target = ROOT / (name + '_annotated.png')
    if target.exists():
        raise FileExistsError(target)
    with Image.open(source) as old:
        rgb = old.convert('RGB')
    width, height = rgb.size
    canvas = Image.new('RGB', (width, height + 260), '#ffffff')
    canvas.paste(rgb, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.rectangle((28, height + 8, width - 28, height + 245), fill='#fff4e6', outline='#a23b17', width=3)
    bold = ImageFont.truetype(FONT_BOLD, 27)
    normal = ImageFont.truetype(FONT, 24)
    y = height + 18
    for line in CAUTIONS:
        d.text((48, y), line, font=bold if line.startswith('CORRECTION') else normal, fill='#6e230e')
        y += 35
    y += 7
    for line in SOURCES:
        d.text((48, y), line, font=normal, fill='#18364b')
        y += 30
    canvas.save(target, optimize=True)
    print(target, canvas.size, target.stat().st_size)
