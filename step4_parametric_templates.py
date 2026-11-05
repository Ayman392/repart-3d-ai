
import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def create_l_bracket(
    length_mm: float = 45.0,
    width_mm: float = 20.0,
    height_mm: float = 30.0,
    thickness_mm: float = 5.0,
    hole_diameter_mm: float = 5.0,
    hole_edge_margin_mm: float = 7.5,
) -> trimesh.Trimesh:
    """
    Create a basic L-bracket with two holes through its horizontal plate.

    Axes:
        X = length
        Y = width
        Z = height

    The horizontal plate sits at the bottom.
    The vertical plate rises along the back edge (positive Y).
    """
    values = [
        length_mm,
        width_mm,
        height_mm,
        thickness_mm,
        hole_diameter_mm,
        hole_edge_margin_mm,
    ]

    if not np.isfinite(values).all():
        raise ValueError("All dimensions must be finite numbers.")

    if min(length_mm, width_mm, height_mm, thickness_mm) <= 0:
        raise ValueError("Bracket dimensions must be positive.")

    if thickness_mm >= min(width_mm, height_mm):
        raise ValueError(
            "Thickness must be smaller than width and height."
        )

    if hole_diameter_mm <= 0:
        raise ValueError("Hole diameter must be positive.")

    radius = hole_diameter_mm / 2.0

    if length_mm <= 2 * hole_edge_margin_mm:
        raise ValueError("Length is too short for the hole edge margins.")

    if hole_edge_margin_mm < radius:
        raise ValueError("Hole edge margin must be at least the hole radius.")

    if width_mm <= 2 * radius:
        raise ValueError("Hole diameter is too large for the plate width.")

    # Horizontal plate: length x width x thickness.
    horizontal = trimesh.creation.box(
        extents=[length_mm, width_mm, thickness_mm]
    )
    horizontal.apply_translation(
        [length_mm / 2, width_mm / 2, thickness_mm / 2]
    )

    # Vertical plate: length x thickness x height.
    # Its bottom overlaps the horizontal plate to form a single solid.
    vertical = trimesh.creation.box(
        extents=[length_mm, thickness_mm, height_mm]
    )
    vertical.apply_translation(
        [
            length_mm / 2,
            width_mm - thickness_mm / 2,
            height_mm / 2,
        ]
    )

    bracket = trimesh.boolean.union(
        [horizontal, vertical],
        engine="manifold",
    )

    if bracket is None or bracket.is_empty:
        raise RuntimeError("Could not create the L-bracket solid.")

    # Cut two holes through the horizontal plate along Z.
    hole_centers_x = [
        hole_edge_margin_mm,
        length_mm - hole_edge_margin_mm,
    ]

    cutters = []

    for x in hole_centers_x:
        cutter = trimesh.creation.cylinder(
            radius=radius,
            height=thickness_mm + 2.0,
            sections=48,
        )
        cutter.apply_translation(
            [x, width_mm / 2, thickness_mm / 2]
        )
        cutters.append(cutter)

    bracket = trimesh.boolean.difference(
        [bracket, *cutters],
        engine="manifold",
    )

    if bracket is None or bracket.is_empty:
        raise RuntimeError("Could not cut the mounting holes.")

    if not bracket.is_watertight or not bracket.is_volume:
        raise RuntimeError("Generated bracket failed mesh validation.")

    expected_extents = np.array(
        [length_mm, width_mm, height_mm],
        dtype=float,
    )

    if not np.allclose(
        bracket.extents,
        expected_extents,
        atol=1e-4,
    ):
        raise RuntimeError(
            f"Unexpected bracket dimensions: {bracket.extents.tolist()}"
        )

    return bracket


def main():
    parser = argparse.ArgumentParser(
        description="Generate and validate a parametric L-bracket STL."
    )
    parser.add_argument("--length", type=float, default=45.0)
    parser.add_argument("--width", type=float, default=20.0)
    parser.add_argument("--height", type=float, default=30.0)
    parser.add_argument("--thickness", type=float, default=5.0)
    parser.add_argument("--hole-diameter", type=float, default=5.0)
    parser.add_argument("--hole-edge-margin", type=float, default=7.5)
    parser.add_argument(
        "--output",
        default="outputs/parametric_l_bracket.stl",
    )
    args = parser.parse_args()

    try:
        mesh = create_l_bracket(
            length_mm=args.length,
            width_mm=args.width,
            height_mm=args.height,
            thickness_mm=args.thickness,
            hole_diameter_mm=args.hole_diameter,
            hole_edge_margin_mm=args.hole_edge_margin,
        )

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(output))

        # Reload the STL to verify the exported geometry independently.
        exported = trimesh.load(str(output), force="mesh")

        report = {
            "status": "success",
            "outputSTL": str(output),
            "dimensionsMm": exported.extents.round(4).tolist(),
            "volumeMm3": round(float(exported.volume), 3),
            "watertight": bool(exported.is_watertight),
            "volumeValid": bool(exported.is_volume),
            "vertices": len(exported.vertices),
            "faces": len(exported.faces),
            "holeDiameterMm": args.hole_diameter,
            "holeCentersXmm": [
                args.hole_edge_margin,
                args.length - args.hole_edge_margin,
            ],
            "notes": [
                "Basic sharp-cornered L-bracket; no reinforcing gussets.",
                "Two holes pass through the horizontal plate.",
                "Verify hole positions and clearances against the real part.",
            ],
        }

        print(json.dumps(report, indent=2))

    except (ValueError, RuntimeError, OSError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
