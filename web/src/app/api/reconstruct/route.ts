import { NextRequest, NextResponse } from "next/server";
import { execFile } from "child_process";
import path from "path";
import fs from "fs/promises";
import { existsSync } from "fs";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const partCategory = (formData.get("partCategory") as string) || "knob";
    const lengthMm = (formData.get("lengthMm") as string) || "40";
    const widthMm = (formData.get("widthMm") as string) || "40";
    const heightMm = (formData.get("heightMm") as string) || "18";
    const holeDiameterMm = (formData.get("holeDiameterMm") as string) || "6";

    const rootDir = path.resolve(process.cwd(), "..");
    const uploadDir = path.join(rootDir, "uploads");
    await fs.mkdir(uploadDir, { recursive: true });

    const files = formData.getAll("photos") as File[];
    const savedImagePaths: string[] = [];

    for (const file of files) {
      if (file && file.size > 0) {
        const buffer = Buffer.from(await file.arrayBuffer());
        const filePath = path.join(uploadDir, `${Date.now()}-${file.name}`);
        await fs.writeFile(filePath, buffer);
        savedImagePaths.push(filePath);
      }
    }

    if (savedImagePaths.length === 0) {
      savedImagePaths.push(
        path.join(rootDir, "dataset", "photos", "P01_stove_knob", "view1_sharp.jpg")
      );
    }

    const stlFileName = `repart_${partCategory}.stl`;
    const publicOutPath = path.join(process.cwd(), "public", "outputs", stlFileName);

    const winPython = path.join(rootDir, "venv", "Scripts", "python.exe");
    const macPython = path.join(rootDir, "venv", "bin", "python");
    const pythonExe = existsSync(winPython)
      ? winPython
      : existsSync(macPython)
      ? macPython
      : "python";

    const scriptPath = path.join(rootDir, "run_web_pipeline.py");
    const args = [
      scriptPath,
      partCategory,
      lengthMm,
      widthMm,
      heightMm,
      holeDiameterMm,
      publicOutPath,
      ...savedImagePaths,
    ];

    const result = await new Promise<Record<string, unknown>>((resolve, reject) => {
      execFile(pythonExe, args, (error, stdout, stderr) => {
        if (error) {
          reject(stderr || error.message);
          return;
        }
        const lastLine = stdout.trim().split("\n").pop() || "{}";
        resolve(JSON.parse(lastLine) as Record<string, unknown>);
      });
    });

    return NextResponse.json({
      ...result,
      stlUrl: `/outputs/${stlFileName}?t=${Date.now()}`,
    });
  } catch (err: unknown) {
    return NextResponse.json(
      { error: "Pipeline failed", details: String(err) },
      { status: 500 }
    );
  }
}