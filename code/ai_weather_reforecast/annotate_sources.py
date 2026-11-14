"""Add a source corner note below existing plots without changing plotted pixels.

Run locally: python3 annotate_sources.py. Refuses to overwrite prior output.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CAPTION = '数据：ERA5（Hersbach et al. 2020, C3S/ARCO）；模型：Pangu-Weather、FuXi（earth2studio）'
FONT = './Windows/Fonts/NotoSansSC-VF.ttf'
PAIRS = [('errors.png', 'errors_sources_v2.png'),
         ('errors_E3_supp.png', 'errors_E3_supp_sources_v2.png')]

for source, target in PAIRS:
    src, dest = ROOT / source, ROOT / target
    if dest.exists():
        raise FileExistsError(f'Will not overwrite {dest}')
    with Image.open(src) as original:
        original = original.convert('RGB')
        font = ImageFont.truetype(FONT, 21)
        pad, footer = 28, 76
        canvas = Image.new('RGB', (original.width, original.height + footer), 'white')
        canvas.paste(original, (0, 0))
        draw = ImageDraw.Draw(canvas)
        box = draw.textbbox((0, 0), CAPTION, font=font)
        width = box[2] - box[0]
        assert width + 2 * pad <= original.width, (source, width, original.width)
        # Right-aligned bottom corner; separate footer retains every original plot pixel.
        draw.text((original.width - pad - width, original.height + 22),
                  CAPTION, font=font, fill=(60, 60, 60))
        canvas.save(dest, format='PNG')
        with Image.open(dest) as verified:
            assert verified.crop((0, 0, original.width, original.height)).tobytes() == original.tobytes()
        print(f'{dest}: {canvas.width}×{canvas.height}, original plot pixels intact')
