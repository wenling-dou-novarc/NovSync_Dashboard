import os
from PIL import Image, ImageChops

def images_are_identical(img1_path: str, img2_path: str, threshold: float = 0.005) -> bool:
    """Returns True if local pixel differences fall below threshold."""
    if not os.path.exists(img1_path) or not os.path.exists(img2_path):
        return False

    with Image.open(img1_path).convert("RGB") as img1, Image.open(img2_path).convert("RGB") as img2:
        if img1.size != img2.size:
            return False

        diff = ImageChops.difference(img1, img2)
        non_zero = sum(1 for pixel in diff.getdata() if any(c > 15 for c in pixel))
        total_pixels = img1.width * img1.height
        return (non_zero / total_pixels) < threshold
