"use client";

import React, { useState, useEffect, useRef } from "react";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Box, AlertTriangle, CheckCircle2, Download, Layers, Sparkles } from "lucide-react";

interface PipelineReport {
  status: string;
  partCategory: string;
  warnings: string[];
  ablation: {
    unconstrainedErrorMm: number;
    constrainedErrorMm: number;
  };
  validation: {
    isWatertight: boolean;
    dimensionsMm: number[];
    holeMm: number;
    filamentGrams: number;
    printTimeMins: number;
    costBdt: number;
  };
  stlUrl: string;
}

export default function RePartStudioPage() {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);

  const [partCategory, setPartCategory] = useState("knob");
  const [lengthMm, setLengthMm] = useState("40.0");
  const [widthMm, setWidthMm] = useState("40.0");
  const [heightMm, setHeightMm] = useState("18.0");
  const [holeDiameterMm, setHoleDiameterMm] = useState("6.0");
  const [photos, setPhotos] = useState<FileList | null>(null);

  const [loading, setLoading] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [report, setReport] = useState<PipelineReport | null>(null);

  // Initialize Three.js Viewport
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x090d16);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, container.clientWidth / 460, 0.1, 1000);
    camera.position.set(55, 45, 55);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, 460);
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.9);
    dirLight.position.set(60, 80, 100);
    scene.add(dirLight);
    scene.add(new THREE.GridHelper(120, 12, 0x3b82f6, 0x1e293b));

    let reqId: number;
    const animate = () => {
      reqId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => cancelAnimationFrame(reqId);
  }, []);

  // Load STL into Three.js whenever report updates
  const loadStlIntoScene = (url: string) => {
    if (!sceneRef.current) return;
    const loader = new STLLoader();
    loader.load(url, (geometry) => {
      if (meshRef.current && sceneRef.current) {
        sceneRef.current.remove(meshRef.current);
      }
      geometry.center();
      const material = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        metalness: 0.25,
        roughness: 0.35,
        wireframe: wireframe,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.rotation.x = -Math.PI / 2;
      meshRef.current = mesh;
      sceneRef.current?.add(mesh);
    });
  };

  const toggleWireframe = () => {
    setWireframe((prev) => {
      const next = !prev;
      if (meshRef.current) {
        (meshRef.current.material as THREE.MeshStandardMaterial).wireframe = next;
      }
      return next;
    });
  };

  const handleReconstruct = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const formData = new FormData();
    formData.append("partCategory", partCategory);
    formData.append("lengthMm", lengthMm);
    formData.append("widthMm", widthMm);
    formData.append("heightMm", heightMm);
    formData.append("holeDiameterMm", holeDiameterMm);
    if (photos) {
      Array.from(photos).forEach((file) => formData.append("photos", file));
    }

    const res = await fetch("/api/reconstruct", { method: "POST", body: formData });
    const data = await res.json();
    setLoading(false);

    if (data.status === "success") {
      setReport(data);
      loadStlIntoScene(data.stlUrl);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-600 rounded-xl shadow-lg shadow-blue-600/30">
              <Box className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">RePart 3D AI Studio</h1>
              <p className="text-xs text-slate-400">
                Multi-View 3D Reconstruction & Measurement-Constrained CAD Pipeline
              </p>
            </div>
          </div>
          <Badge className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-3 py-1">
            Next.js + shadcn/ui + Python Trimesh Active
          </Badge>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Panel: Guided Capture & Caliper Form */}
          <div className="lg:col-span-5 space-y-4">
            <Card className="bg-slate-900 border-slate-800 text-slate-100">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2 text-blue-400">
                  <Sparkles className="w-4 h-4" /> 1. Capture & Caliper Constraints
                </CardTitle>
                <CardDescription className="text-slate-400 text-xs">
                  Upload part photos and enter physical caliper measurements (mm).
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleReconstruct} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs text-slate-300">Part Category</Label>
                    <select
                      value={partCategory}
                      onChange={(e) => setPartCategory(e.target.value)}
                      className="w-full rounded-md bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100"
                    >
                      <option value="knob">Appliance Control Knob / Dial</option>
                      <option value="l_bracket">L-Bracket / Structural Mount</option>
                      <option value="spacer">Cylindrical Bushing / Spacer</option>
                      <option value="cover">Rectangular Cover Plate / Cap</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs text-slate-300">Multi-View Photos (Optional for quick test)</Label>
                    <Input
                      type="file"
                      multiple
                      accept="image/*"
                      onChange={(e) => setPhotos(e.target.files)}
                      className="bg-slate-800 border-slate-700 text-xs text-slate-300 cursor-pointer"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs text-slate-300">Length / Outer Ø (mm)</Label>
                      <Input
                        type="number"
                        step="0.1"
                        value={lengthMm}
                        onChange={(e) => setLengthMm(e.target.value)}
                        className="bg-slate-800 border-slate-700 text-white"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs text-slate-300">Width (mm)</Label>
                      <Input
                        type="number"
                        step="0.1"
                        value={widthMm}
                        onChange={(e) => setWidthMm(e.target.value)}
                        className="bg-slate-800 border-slate-700 text-white"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs text-slate-300">Height / Thickness (mm)</Label>
                      <Input
                        type="number"
                        step="0.1"
                        value={heightMm}
                        onChange={(e) => setHeightMm(e.target.value)}
                        className="bg-slate-800 border-slate-700 text-white"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs text-slate-300">Shaft / Screw Hole Ø (mm)</Label>
                      <Input
                        type="number"
                        step="0.1"
                        value={holeDiameterMm}
                        onChange={(e) => setHoleDiameterMm(e.target.value)}
                        className="bg-slate-800 border-slate-700 text-white"
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold"
                  >
                    {loading ? "Running AI Guardian & Trimesh Engine..." : "⚡ Reconstruct & Constrain 3D Part"}
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Uncertainty & Quality Alerts */}
            {report?.warnings?.map((w: string, i: number) => (
              <Alert key={i} className="bg-amber-500/10 border-amber-500/30 text-amber-300">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle className="text-xs font-bold">Uncertainty / Printability Warning</AlertTitle>
                <AlertDescription className="text-xs">{w}</AlertDescription>
              </Alert>
            ))}

            {/* Manufacturing & Ablation Report Card */}
            {report?.validation && (
              <Card className="bg-slate-900 border-slate-800 text-slate-100">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2 text-emerald-400">
                    <CheckCircle2 className="w-4 h-4" /> Manufacturing & Slicer Validation
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-xs space-y-2 text-slate-300">
                  <div className="grid grid-cols-2 gap-2">
                    <div><b>Watertight:</b> {report.validation.isWatertight ? "✅ YES" : "❌ NO"}</div>
                    <div><b>Dimensions:</b> {report.validation.dimensionsMm.join(" × ")} mm</div>
                    <div><b>Drilled Hole:</b> Ø {report.validation.holeMm} mm</div>
                    <div><b>Print Time:</b> ~{report.validation.printTimeMins} mins</div>
                    <div><b>PLA Filament:</b> {report.validation.filamentGrams} g</div>
                    <div><b>Est. Cost:</b> {report.validation.costBdt} BDT</div>
                  </div>
                  <div className="pt-2 border-t border-slate-800 text-slate-400">
                    <b>RQ2 Ablation:</b> Unconstrained AI Error:{" "}
                    <span className="text-rose-400 font-semibold">{report.ablation.unconstrainedErrorMm} mm</span> → Constrained:{" "}
                    <span className="text-emerald-400 font-semibold">{report.ablation.constrainedErrorMm} mm</span>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Panel: Interactive Three.js 3D Viewport */}
          <div className="lg:col-span-7">
            <Card className="bg-slate-900 border-slate-800 text-slate-100 h-full">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base text-blue-400">2. Interactive 3D CAD Inspector</CardTitle>
                  <CardDescription className="text-xs text-slate-400">
                    Inspect geometry, hole clearance, and mesh topology before exporting.
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={toggleWireframe} className="bg-slate-800 border-slate-700 text-xs">
                    <Layers className="w-3.5 h-3.5 mr-1" /> Wireframe
                  </Button>
                  {report?.stlUrl && (
                    <a href={report.stlUrl} download="replacement_part.stl">
                      <Button size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-xs">
                        <Download className="w-3.5 h-3.5 mr-1" /> Export .STL
                      </Button>
                    </a>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <div ref={mountRef} className="w-full h-115 rounded-lg overflow-hidden border border-slate-800" />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}