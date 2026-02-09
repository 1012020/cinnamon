from PIL import Image
import os

def embed_icc_profile(input_image, output_image, icc_profile):
    # Read ICC profile bytes
    with open(icc_profile, "rb") as f:
        icc_bytes = f.read()

    # Open main image and resize
    img = Image.open(input_image)
    img_resized = img.resize((512, 512), Image.LANCZOS)
    dpi = img.info.get("dpi", (72, 72))

    # Overlay cinnamon.png if available
    cinnamon_path = os.path.join(os.path.dirname(icc_profile), "cinnamon.png")
    if os.path.exists(cinnamon_path):
        cinnamon = Image.open(cinnamon_path)
        if cinnamon.mode != "RGBA":
            cinnamon = cinnamon.convert("RGBA")
        c_width, c_height = cinnamon.size
        pos = (512 - c_width, 512 - c_height)
        img_resized.paste(cinnamon, pos, cinnamon)
        cinnamon.close()
    else:
        print("Warning: cinnamon.png not found, skipping overlay.")

    # Convert all pure black pixels (0,0,0) to (0,0,1)
    if img_resized.mode != "RGBA":
        img_resized = img_resized.convert("RGBA")
    import numpy as np
    arr = np.array(img_resized)
    # Only change pixels where R,G,B are all 0 (ignore alpha)
    mask = (arr[...,0] == 0) & (arr[...,1] == 0) & (arr[...,2] == 0)
    arr[mask, 2] = 1  # Set B to 1
    img_resized = Image.fromarray(arr, "RGBA")

    img_resized.save(
        output_image,
        format="PNG",
        compress_level=9,
        icc_profile=icc_bytes,
        dpi=dpi
    )
    img.close()
    img_resized.close()
