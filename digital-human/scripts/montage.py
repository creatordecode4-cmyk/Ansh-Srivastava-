import sys
from PIL import Image
out=sys.argv[1]; ims=[Image.open(p).convert("RGB") for p in sys.argv[2:]]
h=max(i.height for i in ims); ims=[i.resize((int(i.width*h/i.height),h)) for i in ims]
W=sum(i.width for i in ims); m=Image.new("RGB",(W,h)); x=0
for i in ims: m.paste(i,(x,0)); x+=i.width
m.save(out)
