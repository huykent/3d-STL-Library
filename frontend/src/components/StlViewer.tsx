'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';

interface StlViewerProps {
  modelUrl: string;
}

export function StlViewer({ modelUrl }: StlViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{ faces: number; vertices: number; dimensions: string } | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !modelUrl) return;

    let animationFrameId: number;
    setLoading(true);
    setError(null);

    // 1. Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0e1a);

    // 2. Camera setup
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 5000);

    // 3. WebGL Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // Clear previous children
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // 4. Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 2.0;

    // 5. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.4);
    dirLight1.position.set(100, 150, 100);
    dirLight1.castShadow = true;
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x60a5fa, 0.7);
    dirLight2.position.set(-100, -50, -100);
    scene.add(dirLight2);

    // Grid Floor
    const grid = new THREE.GridHelper(300, 30, 0x3b82f6, 0x1e293b);
    grid.position.y = 0;
    scene.add(grid);

    // 6. Load STL Model
    let mesh: THREE.Mesh | null = null;
    const loader = new STLLoader();

    loader.load(
      modelUrl,
      (geometry) => {
        geometry.computeVertexNormals();
        geometry.computeBoundingBox();

        const bbox = geometry.boundingBox!;
        const center = new THREE.Vector3();
        bbox.getCenter(center);

        // Center X and Z, put Y base on the grid floor (y = 0)
        const size = new THREE.Vector3();
        bbox.getSize(size);
        geometry.translate(-center.x, -bbox.min.y, -center.z);

        // Position camera to frame the model nicely
        const maxDim = Math.max(size.x, size.y, size.z) || 10;
        camera.position.set(maxDim * 1.5, maxDim * 1.3, maxDim * 1.8);
        camera.lookAt(0, size.y / 2, 0);
        controls.target.set(0, size.y / 2, 0);
        controls.update();

        // Model Material: Sleek metallic resin style
        const material = new THREE.MeshStandardMaterial({
          color: 0x818cf8,
          roughness: 0.35,
          metalness: 0.25,
        });

        mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        scene.add(mesh);

        // Calculate statistics
        const faces = geometry.attributes.position ? geometry.attributes.position.count / 3 : 0;
        const vertices = geometry.attributes.position ? geometry.attributes.position.count : 0;
        setStats({
          faces: Math.round(faces),
          vertices,
          dimensions: `${size.x.toFixed(1)} x ${size.y.toFixed(1)} x ${size.z.toFixed(1)} mm`,
        });

        setLoading(false);
      },
      undefined,
      (err) => {
        console.error('Error loading STL in Three.js:', err);
        setError('Không thể tải hoặc hiển thị file STL này.');
        setLoading(false);
      }
    );

    // 7. Animation loop
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // 8. Resize handler
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      controls.dispose();
      renderer.dispose();
      if (mesh) {
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      }
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [modelUrl]);

  return (
    <div className="w-full h-full min-h-[550px] bg-[#0a0e1a] rounded-xl overflow-hidden border border-white/10 relative group">
      <div ref={containerRef} className="w-full h-full min-h-[550px]" />

      {loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 backdrop-blur-sm gap-3 z-10">
          <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium text-blue-300">Đang tải mô hình 3D...</span>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 backdrop-blur-sm gap-2 z-10 text-red-400">
          <span className="text-sm">{error}</span>
        </div>
      )}

      {stats && !loading && (
        <div className="absolute bottom-3 left-3 bg-black/75 backdrop-blur-md px-3.5 py-2 rounded-lg border border-white/10 text-xs text-gray-300 flex gap-4 pointer-events-none z-10 shadow-lg">
          <div><span className="text-gray-500">Số mặt:</span> <span className="text-white font-semibold">{stats.faces.toLocaleString()}</span></div>
          <div><span className="text-gray-500">Kích thước:</span> <span className="text-white font-semibold">{stats.dimensions}</span></div>
        </div>
      )}

      <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 text-[11px] text-gray-400 pointer-events-none z-10">
        🖱️ Chuột trái: Xoay | Chuột phải: Di chuyển | Cuộn: Thu phóng
      </div>
    </div>
  );
}
