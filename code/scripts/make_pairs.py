#!/usr/bin/env python3
"""Render ≤100KB review cards from verified remote thumbnail copies."""
import argparse,csv,textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

def main():
    p=argparse.ArgumentParser();p.add_argument('--csv',required=True);p.add_argument('--thumbs',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
    with open(a.csv,newline='') as f:rows=list(csv.DictReader(f))
    for i,row in enumerate(rows,1):
        src=Path(a.thumbs)/row['thumb_path'];image=Image.open(src).convert('RGB');image.thumbnail((512,440))
        caption=row['caption_text'];lines=textwrap.wrap(caption,width=75,break_long_words=True)[:5]
        canvas=Image.new('RGB',(max(512,image.width),image.height+20+20*len(lines)),'white');canvas.paste(image,((canvas.width-image.width)//2,0))
        d=ImageDraw.Draw(canvas)
        for k,line in enumerate(lines):d.text((5,image.height+5+k*20),line,font=font,fill='black')
        path=out/f'{i:02d}_{row["fig_id"]}.jpg'
        for q in [76,65,50,35]:
            canvas.save(path,'JPEG',quality=q,optimize=True)
            if path.stat().st_size<=100000:break
        if path.stat().st_size>100000:raise RuntimeError(f'card too big {path}')
    print('rendered',len(rows),'cards; max bytes',max(x.stat().st_size for x in out.glob('*.jpg')))
if __name__=='__main__':main()
