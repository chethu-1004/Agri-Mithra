import numpy as np
from PIL import Image

def prepare_image(path,image_size=(224,224)):
    """Load one already-uploaded image as EfficientNetB0-compatible RGB pixels in [0,255]."""
    with Image.open(path) as image:
        rgb=image.convert('RGB').resize((image_size[1],image_size[0]))
        array=np.asarray(rgb,dtype='float32')
    return array[None,...]
