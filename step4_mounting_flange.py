
import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def validate_parameters(
    length,
    width,
    thickness,
    opening_length,
    opening_width,
    hole_diameter,
    edge_margin,
):
    """Validate all mounting flange dimensions."""

    values = {
        "length": length,
        "width": width,
        "thickness": thickness,
        "opening_length": opening_length,
        "opening_width": opening_width,
        "hole_diameter": hole_diameter,
        "edge_margin": edge_margin,
    }

    for name, value in values.items():
        if not np.isfinite(value) or value <= 0:
            raise ValueError(
                f"{name} must be a finite positive number."
            )

    if opening_length >= length:
        raise ValueError("Opening length must be smaller than flange length.")

    if opening_width >= width:
        raise ValueError("Opening width must be smaller than flange width.")

    if hole_diameter >= min(length, width):
        raise ValueError("Hole diameter is too large.")

    hole_radius = hole_diameter / 2

    if edge_margin <= hole_radius:
        raise ValueError("Edge margin must be greater than hole radius.")

    hole_x = length / 2 - edge_margin
    hole_y = width / 2 - edge_margin

    if hole_x - hole_radius <= opening_length / 2:
        raise ValueError("Mounting holes overlap the central opening along X.")

    if hole_y - hole_radius <= opening_width / 2:
        raise ValueError("Mounting holes overlap the central opening along Y.")

    return True


def create_mounting_flange(
    length=60.0,
    width=40.0,
    thickness=5.0,
    opening_length=20.0,
    opening_width=12.0,
    hole_diameter=5.0,
    edge_margin=7.5,
):
    """Generate a rectangular flange with five through-openings."""

    validate_parameters(
        length,
        width,
        thickness,
        opening_length,
        opening_width,
        hole_diameter,
        edge_margin,
    )

    # Create the main rectangular plate, centered at the origin.
    plate = trimesh.creation.box(
        extents=[length, width, thickness]
    )

    # Calculate the four symmetric mounting hole positions.
    hole_x = length / 2 - edge_margin
    hole_y = width / 2 - edge_margin

    hole_positions = [
        (-hole_x, -hole_y),
        (hole_x, -hole_y),
        (-hole_x, hole_y),
        (hole_x, hole_y),
    ]

    cutters = []

    # Central rectangular opening.
    opening = trimesh.creation.box(
        extents=[
            opening_length,
            opening_width,
            thickness + 2,
        ]
    )
    cutters.append(opening)

    # Four cylindrical mounting holes.
    for x, y in hole_positions:
        hole = trimesh.creation.cylinder(
            radius=hole_diameter / 2,
            height=thickness + 2,
            sections=64,
        )

        hole.apply_translation([x, y, 0])
        cutters.append(hole)

    # Combine all cutting meshes.
    cutting_mesh = trimesh.util.concatenate(cutters)

    # Subtract openings from the main plate.
    flange = trimesh.boolean.difference(
        [plate, cutting_mesh],
        engine="manifold",
    )

    if flange is None or flange.is_empty:
        raise RuntimeError("Flange Boolean operation failed.")

    return flange, hole_positions


def validate_mesh(mesh, expected_dimensions):
    """Check mesh integrity and dimensional accuracy."""

    if mesh is None or mesh.is_empty:
        raise ValueError("Generated mesh is empty.")

    actual_dimensions = mesh.extents

    dimensional_error = np.abs(
        actual_dimensions - expected_dimensions
    )

    report = {
        "watertight": bool(mesh.is_watertight),
        "volumeValid": bool(mesh.is_volume),
        "windingConsistent": bool(mesh.is_winding_consistent),
        "actualDimensionsMm": actual_dimensions.round(3).tolist(),
        "expectedDimensionsMm": np.asarray(
            expected_dimensions
        ).round(3).tolist(),
        "dimensionalErrorMm": dimensional_error.round(3).tolist(),
        "maximumDimensionalErrorMm": round(
            float(dimensional_error.max()), 3
        ),
        "volumeMm3": round(float(mesh.volume), 3),
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
               "boundaryEdges": int(
            np.sum(
                np.bincount(mesh.edges_unique_inverse) == 1
            )
        ),
        "nonManifoldEdges": int(
            np.sum(
                np.bincount(mesh.edges_unique_inverse) > 2
            )
        ),
    }

    if not mesh.is_watertight:
        raise ValueError("Mesh is not watertight.")

    if not mesh.is_volume:
        raise ValueError("Mesh is not a valid volume.")

    if not mesh.is_winding_consistent:
        raise ValueError("Mesh winding is inconsistent.")

    if dimensional_error.max() > 0.01:
        raise ValueError("Generated mesh dimensions are incorrect.")

    return report


def generate_and_export(args):
    """Generate, validate, export, and reload the mounting flange."""

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    expected_dimensions = np.array([
        args.length,
        args.width,
        args.thickness,
    ])

    flange, hole_positions = create_mounting_flange(
        length=args.length,
        width=args.width,
        thickness=args.thickness,
        opening_length=args.opening_length,
        opening_width=args.opening_width,
        hole_diameter=args.hole_diameter,
        edge_margin=args.edge_margin,
    )

    # Validate the generated mesh.
    validation_report = validate_mesh(
        flange,
        expected_dimensions,
    )

    # Export STL.
    flange.export(output_path)

    # Reload STL independently to verify the exported file.
    reloaded_mesh = trimesh.load_mesh(
        output_path,
        force="mesh",
        process=True,
    )

    reload_report = validate_mesh(
        reloaded_mesh,
        expected_dimensions,
    )

    report = {
        "status": "success",
        "outputSTL": str(output_path),
        "dimensionsMm": expected_dimensions.tolist(),
        "openingDimensionsMm": [
            args.opening_length,
            args.opening_width,
        ],
        "holeDiameterMm": args.hole_diameter,
        "holeCount": len(hole_positions),
        "holePositionsMm": [
            [round(x, 3), round(y, 3)]
            for x, y in hole_positions
        ],
        "meshValidation": validation_report,
        "exportValidation": reload_report,
        "notes": [
            "Rectangular mounting flange with four circular mounting holes.",
            "One central rectangular through-opening.",
            "Mechanical strength and real-world fit require physical verification.",
        ],
    }

    print(json.dumps(report, indent=4))


def main():
    parser = argparse.ArgumentParser(
        description="Parametric rectangular mounting flange generator"
    )

    parser.add_argument("--length", type=float, default=60.0)
    parser.add_argument("--width", type=float, default=40.0)
    parser.add_argument("--thickness", type=float, default=5.0)

    parser.add_argument("--opening-length", type=float, default=20.0)
    parser.add_argument("--opening-width", type=float, default=12.0)

    parser.add_argument("--hole-diameter", type=float, default=5.0)
    parser.add_argument("--edge-margin", type=float, default=7.5)

    parser.add_argument(
        "--output",
        type=str,
        default="outputs/parametric_mounting_flange.stl",
    )

    args = parser.parse_args()

    try:
        generate_and_export(args)

    except Exception as error:
        print(
            json.dumps({
                "status": "error",
                "message": str(error),
            }, indent=4)
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
