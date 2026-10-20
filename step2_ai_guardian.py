import os
import json
import cv2
import numpy as np
from rembg import remove
from PIL import Image

def check_capture_and_segment(part_folder: str, required_dims: dict, output_dir: str = "outputs/segmented"):
    os.makedirs(output_dir, exist_ok=True)
    
    warnings = []
    photo_reports = []
    valid_descriptors = []
    orb = cv2.ORB_create(nfeatures=500)

    image_files = sorted([
        f for f in os.listdir(part_folder) 
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    print(f"\n=======================================================")
    print(f"🔍 [AI Guardian] Inspecting {len(image_files)} photos in: {part_folder}")
    print(f"=======================================================")

    # 1. Check View Count (Uncertainty Check - Section 5.3)
    if len(image_files) < 2:
        warnings.append("Uncertainty Alert: Fewer than 2 views uploaded. Hidden geometry cannot be verified.")

    for idx, filename in enumerate(image_files):
        img_path = os.path.join(part_folder, filename)
        img_cv = cv2.imread(img_path)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # 2. Blur Detection (Laplacian Variance)
        blur_score = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1)
        is_blurry = blur_score < 50.0

        status_icon = "❌ BLURRY (REJECTED)" if is_blurry else "✅ SHARP (ACCEPTED)"
        print(f"  • {filename}: Blur Score = {blur_score} -> {status_icon}")

        if is_blurry:
            warnings.append(f"Rejected '{filename}' due to motion/focus blur (score: {blur_score}). Retake photo.")
            photo_reports.append({"file": filename, "blur_score": blur_score, "accepted": False})
            continue

        # 3. AI Background Removal (rembg U2-Net) on accepted sharp images
        pil_img = Image.open(img_path).convert("RGBA")
        segmented_img = remove(pil_img)
        clean_path = os.path.join(output_dir, f"clean_{filename}.png")
        segmented_img.save(clean_path)

        # Check object coverage ratio in frame
        alpha_mask = np.array(segmented_img)[:, :, 3]
        coverage_pct = round((np.count_nonzero(alpha_mask > 127) / alpha_mask.size) * 100, 1)
        if coverage_pct < 5.0:
            warnings.append(f"Low coverage in '{filename}' ({coverage_pct}% of frame). Move camera closer.")

        # Extract ORB keypoints for multi-view overlap verification
        kp, des = orb.detectAndCompute(gray, None)
        if des is not None:
            valid_descriptors.append((filename, des))

        photo_reports.append({
            "file": filename,
            "blur_score": blur_score,
            "coverage_percent": coverage_pct,
            "accepted": True,
            "segmented_mask_path": clean_path
        })

    # 4. Check Feature Overlap Between Accepted Views
    overlap_scores = []
    if len(valid_descriptors) >= 2:
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        for i in range(len(valid_descriptors) - 1):
            f1, des1 = valid_descriptors[i]
            f2, des2 = valid_descriptors[i + 1]
            matches = bf.match(des1, des2)
            good_matches = [m for m in matches if m.distance < 55]
            overlap_scores.append({"pair": f"{f1} <-> {f2}", "matched_features": len(good_matches)})

    # 5. Verify Required Caliper Measurements
    for dim_key, dim_val in required_dims.items():
        if dim_val is None or dim_val <= 0:
            warnings.append(f"Missing critical measurement: '{dim_key}'. Please measure with calipers.")

    accepted_count = sum(1 for p in photo_reports if p["accepted"])
    ready_for_3d = accepted_count >= 1 and all(v > 0 for v in required_dims.values())

    result = {
        "ready_for_3d_reconstruction": ready_for_3d,
        "accepted_photos_count": accepted_count,
        "rejected_photos_count": len(image_files) - accepted_count,
        "photo_details": photo_reports,
        "view_overlap_checks": overlap_scores,
        "warnings_and_prompts": warnings
    }

    print(f"\n📊 Summary: {accepted_count} Accepted, {len(image_files) - accepted_count} Rejected.")
    for w in warnings:
        print(f"  ⚠️ {w}")
    return result

if __name__ == "__main__":
    # Test on Part P01 (Stove Knob) from our generated dataset
    sample_folder = "dataset/photos/P01_stove_knob"
    sample_measurements = {"length_mm": 40.0, "width_mm": 40.0, "height_mm": 18.0, "hole_mm": 6.0}
    
    report = check_capture_and_segment(sample_folder, sample_measurements)
    
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/step2_guardian_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\n✅ Saved full AI Guardian report to: outputs/step2_guardian_report.json")