import os
import cv2
import numpy as np
from rembg import remove
from PIL import Image

def process_real_world_photos(input_folder: str, output_folder: str = "dataset/real_processed"):
    os.makedirs(output_folder, exist_ok=True)
    
    if not os.path.exists(input_folder):
        print(f"⚠️ Input folder '{input_folder}' not found. Create it and add your phone photos!")
        return

    image_files = [f for f in os.listdir(input_folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    print(f"\n📸 [Talha's Dataset Tool] Processing {len(image_files)} real-world photos...")

    for filename in image_files:
        path = os.path.join(input_folder, filename)
        img_cv = cv2.imread(path)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # 1. Blur Check (Section 5.3)[cite: 9]
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_sharp = blur_score >= 50.0
        
        print(f"  • {filename}: Blur Score = {blur_score:.1f} -> {'✅ ACCEPTED'}")

        if is_sharp:
            # 2. AI Background Removal (Section 1.7)[cite: 4]
            pil_img = Image.open(path).convert("RGBA")
            cleaned = remove(pil_img)
            out_path = os.path.join(output_folder, f"clean_{filename}.png")
            cleaned.save(out_path)
            print(f"    -> Segmented mask saved to: {out_path}")

    print("\n✅ Real-world photo batch processing complete!")

if __name__ == "__main__":
    # Talha can put his phone photos in a folder named 'real_phone_photos'
    process_real_world_photos("real_phone_photos")