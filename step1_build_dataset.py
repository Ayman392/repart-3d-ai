import os
import csv
import cv2
import numpy as np
import trimesh

def generate_dataset():
    base_dir = "dataset"
    os.makedirs(f"{base_dir}/ground_truth_stl", exist_ok=True)
    os.makedirs(f"{base_dir}/photos", exist_ok=True)

    parts = [
        {"id": "P01", "name": "stove_knob", "cat": "knob", "L": 40.0, "W": 40.0, "H": 18.0, "hole": 6.0},
        {"id": "P02", "name": "volume_dial", "cat": "knob", "L": 28.0, "W": 28.0, "H": 15.0, "hole": 6.0},
        {"id": "P03", "name": "shelf_bracket", "cat": "l_bracket", "L": 45.0, "W": 20.0, "H": 30.0, "hole": 5.0},
        {"id": "P04", "name": "nylon_spacer", "cat": "spacer", "L": 18.0, "W": 18.0, "H": 12.0, "hole": 5.0},
        {"id": "P05", "name": "battery_cover", "cat": "cover", "L": 55.0, "W": 32.0, "H": 4.0, "hole": 3.0},
    ]

    csv_path = f"{base_dir}/ground_truth_measurements.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["part_id", "name", "category", "length_mm", "width_mm", "height_mm", "hole_mm", "stl_path"])

        for p in parts:
            # 1. Create Ground Truth 3D CAD Model
            if p["cat"] in ["knob", "spacer"]:
                mesh = trimesh.creation.cylinder(radius=p["L"]/2.0, height=p["H"], sections=64)
            elif p["cat"] == "l_bracket":
                t = 4.0
                b1 = trimesh.creation.box(extents=[p["L"], p["W"], t])
                b1.apply_translation([0, 0, -p["H"]/2.0 + t/2.0])
                b2 = trimesh.creation.box(extents=[t, p["W"], p["H"]])
                b2.apply_translation([-p["L"]/2.0 + t/2.0, 0, 0])
                mesh = b1.union(b2)
            else:
                mesh = trimesh.creation.box(extents=[p["L"], p["W"], p["H"]])

            if p["hole"] > 0:
                drill = trimesh.creation.cylinder(radius=p["hole"]/2.0, height=p["H"]*3.0, sections=64)
                mesh = mesh.difference(drill)

            stl_path = f"{base_dir}/ground_truth_stl/{p['id']}_{p['name']}.stl"
            mesh.export(stl_path)

            # 2. Create Clear & Blurry Test Photos for Each Part
            part_dir = f"{base_dir}/photos/{p['id']}_{p['name']}"
            os.makedirs(part_dir, exist_ok=True)

            canvas = np.full((512, 512, 3), 235, dtype=np.uint8)
            rx, ry = int(p["L"] * 3), int(p["W"] * 3)
            if p["cat"] in ["knob", "spacer"]:
                cv2.circle(canvas, (256, 256), rx, (50, 100, 200), -1)
            else:
                cv2.rectangle(canvas, (256 - rx, 256 - ry), (256 + rx, 256 + ry), (60, 140, 80), -1)
            if p["hole"] > 0:
                cv2.circle(canvas, (256, 256), int(p["hole"] * 3), (235, 235, 235), -1)

            # Add slight texture for sharp image
            noise = np.random.randint(-15, 15, canvas.shape, dtype=np.int16)
            sharp_img = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            cv2.imwrite(f"{part_dir}/view1_sharp.jpg", sharp_img)
            cv2.imwrite(f"{part_dir}/view2_sharp.jpg", sharp_img)

            # Create an intentionally blurry image to test the AI Blur Detector
            blurry_img = cv2.GaussianBlur(sharp_img, (31, 31), 10)
            cv2.imwrite(f"{part_dir}/view3_blurry.jpg", blurry_img)

            writer.writerow([p["id"], p["name"], p["cat"], p["L"], p["W"], p["H"], p["hole"], stl_path])

    print("SUCCESS: Dataset created inside the 'dataset/' folder!")

if __name__ == "__main__":
    generate_dataset()