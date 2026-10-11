#!/usr/bin/env python3
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1]
src=root/'medical-live-mapping-20261010'/'medical-live-map-20261010.pgm'
out=root/'medical-live-mapping-20261010'/'medical-live-map-smooth-preview.png'
im=Image.open(src).convert('L'); im.resize((im.width*8,im.height*8),Image.Resampling.BICUBIC).save(out)
print(out)
