import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import trimesh

def parse_gcode_metrics(
    gcode_path: str,
    material_cost_bdt_per_gram: float = 2.5,
) -> dict:
    """Extract slicer metrics and estimate material cost in BDT."""
    path = Path(gcode_path)

    if not path.is_file():
        raise FileNotFoundError(f"G-code file not found: {path}")

    if not np.isfinite(material_cost_bdt_per_gram) or material_cost_bdt_per_gram < 0:
        raise ValueError("Material cost per gram must be finite and non-negative.")

    text = path.read_text(encoding="utf-8", errors="replace")

    def find_number(pattern: str):
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        return float(match.group(1)) if match else None

    filament_grams = find_number(
        r"^;\s*total filament used \[g\]\s*=\s*([\d.]+)"
    )

    filament_cm3 = find_number(
        r"^;\s*filament used \[cm3\]\s*=\s*([\d.]+)"
    )

    time_match = re.search(
        r"^;\s*estimated printing time \(normal mode\)\s*=\s*(.+)$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    if filament_grams is None:
        raise ValueError("G-code does not contain total filament mass.")

    if time_match is None:
        raise ValueError("G-code does not contain estimated print time.")

    time_text = time_match.group(1).strip()

    hours = re.search(r"(\d+)\s*h", time_text)
    minutes = re.search(r"(\d+)\s*m", time_text)
    seconds = re.search(r"(\d+)\s*s", time_text)

    total_seconds = (
        (int(hours.group(1)) * 3600 if hours else 0)
        + (int(minutes.group(1)) * 60 if minutes else 0)
        + (int(seconds.group(1)) if seconds else 0)
    )

    return {
        "filamentVolumeCm3": filament_cm3,
        "filamentMassGrams": round(filament_grams, 3),
        "estimatedPrintTime": time_text,
        "estimatedPrintTimeMinutes": round(total_seconds / 60, 2),
        "materialCostBdt": round(
            filament_grams * material_cost_bdt_per_gram, 2
        ),
        "materialCostRateBdtPerGram": material_cost_bdt_per_gram,
        "costNote": (
            "Estimated filament material cost only; excludes electricity, "
            "machine wear, and failed prints."
        ),
    }

def slice_stl(
    stl_path: str,
    config_path: str,
    slicer_executable: str = (
        r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe"
    ),
) -> dict:
    """Slice an STL with PrusaSlicer and return the generated G-code path."""
    stl = Path(stl_path)
    config = Path(config_path)
    slicer = Path(slicer_executable)

    if not stl.is_file():
        raise FileNotFoundError(f"STL file not found: {stl}")

    if not config.is_file():
        raise FileNotFoundError(f"Slicer configuration not found: {config}")

    if not slicer.is_file():
        raise FileNotFoundError(
            f"PrusaSlicer executable not found: {slicer}"
        )

    result = subprocess.run(
        [
            str(slicer),
            "--load",
            str(config.resolve()),
            "--export-gcode",
            str(stl.resolve()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    # PrusaSlicer normally writes G-code beside the input STL.
    gcode_path = stl.with_suffix(".gcode")

    if result.returncode != 0:
        raise RuntimeError(
            "PrusaSlicer failed.\n"
            f"Exit code: {result.returncode}\n"
            f"Details: {result.stderr[-2000:]}"
        )

    if not gcode_path.is_file():
        raise RuntimeError(
            f"PrusaSlicer finished but G-code was not found: {gcode_path}"
        )

    return {
        "status": "success",
        "inputStl": str(stl),
        "gcodePath": str(gcode_path),
        "slicerExecutable": str(slicer),
        "message": "G-code generated successfully.",
    }



def load_mesh(mesh_path: str) -> trimesh.Trimesh:
    """Load an STL/mesh and reject empty or invalid input."""
    path = Path(mesh_path)

    if not path.is_file():
        raise FileNotFoundError(f"Input mesh not found: {path}")

    mesh = trimesh.load(str(path), force="mesh", process=True)

    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
        raise ValueError(f"Input contains no usable mesh: {path}")

    if not np.isfinite(mesh.vertices).all():
        raise ValueError("Mesh contains non-finite vertex coordinates.")

    return mesh


def validate_mesh(mesh: trimesh.Trimesh) -> dict:
    """Check watertightness, edge topology, and basic mesh validity."""
    edges = np.sort(mesh.edges, axis=1)
    _, edge_counts = np.unique(edges, axis=0, return_counts=True)

    return {
        "isWatertight": bool(mesh.is_watertight),
        "isWindingConsistent": bool(mesh.is_winding_consistent),
        "isVolumeValid": bool(mesh.is_volume),
        "boundaryEdgeCount": int(np.count_nonzero(edge_counts == 1)),
        "nonManifoldEdgeCount": int(np.count_nonzero(edge_counts > 2)),
        "vertexCount": int(len(mesh.vertices)),
        "faceCount": int(len(mesh.faces)),
    }


def constrain_dimensions(
    mesh: trimesh.Trimesh,
    target_dimensions_mm: tuple[float, float, float],
) -> dict:
    """
    Scale mesh X/Y/Z extents to measured length/width/height.

    Assumes the input mesh axes already correspond to the target axes.
    This constrains the bounding box; it does not recover missing features.
    """
    target = np.asarray(target_dimensions_mm, dtype=float)

    if target.shape != (3,) or not np.isfinite(target).all():
        raise ValueError("Provide exactly three finite target dimensions.")

    if np.any(target <= 0):
        raise ValueError("Target dimensions must be greater than zero.")

    original = np.asarray(mesh.extents, dtype=float)

    if not np.isfinite(original).all() or np.any(original <= 0):
        raise ValueError("Input mesh must have three positive finite extents.")

    scale_factors = target / original

    # Apply coordinate-wise scaling directly to vertices.
    # This avoids relying on trimesh's non-uniform apply_scale path.
    mesh.vertices = np.asarray(mesh.vertices) * scale_factors

    actual = np.asarray(mesh.extents, dtype=float)
    absolute_error = np.abs(actual - target)

    return {
        "originalDimensionsMm": original.round(4).tolist(),
        "targetDimensionsMm": target.tolist(),
        "scaleFactors": scale_factors.round(8).tolist(),
        "constrainedDimensionsMm": actual.round(4).tolist(),
        "absoluteDimensionalErrorMm": absolute_error.round(6).tolist(),
        "maximumDimensionalErrorMm": float(absolute_error.max()),
    }



def constrain_and_validate(
    input_path: str,
    output_path: str,
    length_mm: float,
    width_mm: float,
    height_mm: float,
    slice_after_export: bool = False,
    slicer_config_path: str = r"outputs\step4_cli_config_pla.ini",
    slicer_executable: str = (
        r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe"
    ),
    material_cost_bdt_per_gram: float = 2.5,
) -> dict:
    """Constrain mesh dimensions, validate it, and optionally slice it."""
    mesh = load_mesh(input_path)

    before_validation = validate_mesh(mesh)

    dimensions_report = constrain_dimensions(
        mesh,
        (length_mm, width_mm, height_mm),
    )

    after_validation = validate_mesh(mesh)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(output))

    report = {
        "status": "success",
        "inputMesh": str(input_path),
        "outputMesh": str(output),
        "dimensions": dimensions_report,
        "validationBefore": before_validation,
        "validationAfter": after_validation,
        "notes": [
            "Scaling constrains outer bounding-box dimensions only.",
            "Hole geometry, wall thickness, and mating surfaces are not "
            "automatically corrected.",
            "Input axes must correspond to length, width, and height.",
        ],
    }

    if slice_after_export:
        slicing_report = slice_stl(
            str(output),
            slicer_config_path,
            slicer_executable,
        )
        metrics = parse_gcode_metrics(
            slicing_report["gcodePath"],
            material_cost_bdt_per_gram,
        )
        report["slicing"] = slicing_report
        report["printMetrics"] = metrics

    return report






def main():
    parser = argparse.ArgumentParser(
        description="Constrain, validate, and optionally slice a 3D mesh."
    )
    parser.add_argument("input_stl", help="Path to input STL mesh")
    parser.add_argument("length_mm", type=float, help="Target X extent")
    parser.add_argument("width_mm", type=float, help="Target Y extent")
    parser.add_argument("height_mm", type=float, help="Target Z extent")
    parser.add_argument("output_stl", help="Path to output STL mesh")

    parser.add_argument(
        "--slice",
        action="store_true",
        help="Generate G-code and report print metrics with PrusaSlicer",
    )
    parser.add_argument(
        "--slicer-config",
        default=r"outputs\step4_cli_config_pla.ini",
        help="Path to the PrusaSlicer configuration file",
    )
    parser.add_argument(
        "--slicer-executable",
        default=(
            r"C:\Program Files\Prusa3D\PrusaSlicer"
            r"\prusa-slicer-console.exe"
        ),
        help="Path to the PrusaSlicer console executable",
    )
    parser.add_argument(
        "--material-cost-bdt-per-gram",
        type=float,
        default=2.5,
        help="Assumed filament material cost in BDT per gram",
    )

    args = parser.parse_args()

    try:
        report = constrain_and_validate(
            args.input_stl,
            args.output_stl,
            args.length_mm,
            args.width_mm,
            args.height_mm,
            slice_after_export=args.slice,
            slicer_config_path=args.slicer_config,
            slicer_executable=args.slicer_executable,
            material_cost_bdt_per_gram=args.material_cost_bdt_per_gram,
        )
        print(json.dumps(report, indent=2))

    except (ValueError, FileNotFoundError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        raise SystemExit(1)




if __name__ == "__main__":
    main()
