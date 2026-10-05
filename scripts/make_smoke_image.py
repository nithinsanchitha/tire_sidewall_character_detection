from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
out=Path('data/synthetic-ocr-smoke.png');out.parent.mkdir(exist_ok=True)
im=Image.new('RGB',(1200,500),'white');d=ImageDraw.Draw(im)
font=ImageFont.truetype('DejaVuSans.ttf',48)
for y,text in [(35,'SYNTHETIC OCR TEST - NOT A TIRE'),(145,'MICHELIN'),(250,'205/55 R16 91V'),(355,'DOT ABCD EF 2323')]:d.text((40,y),text,font=font,fill='black')
im.save(out);print(out)
