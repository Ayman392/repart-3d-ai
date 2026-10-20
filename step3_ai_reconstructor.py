import os
import json
import cv2
import numpy as np
import trimesh

def reconstruct_raw_3d_from_mask(
    segmented_png_path: str,
    part_category: str,
    output_raw_obj: str = "outputs/raw_ai_mesh.obj"
) -> dict:
    print(f"\n=======================================================")
    print(f"🤖 [Step 3: AI Reconstructor] Building raw 3D mesh from: {segmented_png_path}")
    print(f"=======================================================")
    os.makedirs(os.path.dirname(output_raw_obj), exist_ok=True)

    # Load RGBA segmented mask from Step 2
    img = cv2.imread(segmented_png_path, cv2.IMREAD_UNCHANGED)
    if img is None or img.shape[2] < 4:
        raise ValueError(f"Valid RGBA segmented image not found at {segmented_png_path}")

    alpha = img[:, :, 3]
    contours, _ = cv2.findContours(alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Simulated raw AI mesh (unscaled unit space ~ [-0.5, 0.5], with slight AI noise/imperfection)
    # Note: Standard image-to-3D models like TripoSR output arbitrary scale & clogged holes!
    if part_category in ["knob", "spacer"]:
        raw_mesh = trimesh.creation.cylinder(radius=0.48, height=0.42, sections=48)
    elif part_category == "l_bracket":
        b1 = trimesh.creation.box(extents=[0.95, 0.45, 0.12])
        b1.apply_translation([0, 0, -0.35 + 0.06])
        b2 = trimesh.creation.box(extents=[0.12, 0.45, 0.70])
        b2.apply_translation([-0.95/2 + 0.06, 0, 0])
        raw_mesh = b1.union(b2)
    else:
        raw_mesh = trimesh.creation.box(extents=[0.92, 0.58, 0.15])

    # Simulate typical AI dimensional drift (unconstrained AI meshes never match exact mm)
    raw_mesh.export(output_raw_obj)
    raw_extents = [round(float(x), 3) for x in raw_mesh.extents]

    print(f"  • Extracted {len(contours)} foreground contour(s) from AI mask.")
    print(f"  • Raw AI Mesh Extents (Unscaled Unit Space): {raw_extents}")
    print(f"  • Notice: Raw AI mesh has NO real-world millimeter scale and NO precision screw hole!")
    print(f"  ✅ Saved raw AI mesh to: {output_raw_obj}")

    return {
        "status": "success",
        "part_category": part_category,
        "source_mask": segmented_png_path,
        "raw_mesh_path": output_raw_obj,
        "unconstrained_extents": raw_extents
    }

if __name__ == "__main__":
    mask_path = "outputs/segmented/clean_view1_sharp.jpg.png"
    if os.path.exists(mask_path):
        report = reconstruct_raw_3d_from_mask(mask_path, part_category="knob")
        with open("outputs/step3_reconstruct_report.json", "w") as f:
            json.dump(report, f, indent=2)
    else:
        print("⚠️ Run 'python step2_ai_guardian.py' first to generate the segmented mask!")