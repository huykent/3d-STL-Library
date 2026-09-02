'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { ThreeMFLoader } from 'three/examples/jsm/loaders/3MFLoader.js';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';

interface StlViewerProps {
  modelUrl: string;
  fileExtension?: string;
  filename?: string;
  onSpecsComputed?: (specs: { faces: number; vertices: number; bbox_x: number; bbox_y: number; bbox_z: number }) => void;
}

export function StlViewer({ modelUrl, fileExtension, filename, onSpecsComputed }: StlViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{ faces: number; vertices: number; dimensions: string } | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !modelUrl) return;

    let animationFrameId: number;
    let isCancelled = false;
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
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
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

    let loadedObject: THREE.Object3D | null = null;

    // 6. Load Model based on format
    const loadModel = async () => {
      try {
        let ext = (fileExtension || '').toLowerCase().replace('.', '').trim();
        if (!ext && filename) {
          const parts = filename.split('.');
          if (parts.length > 1) ext = parts.pop()!.toLowerCase().trim();
        }

        // Check magic bytes if format is uncertain
        let isZip = false;
        try {
          const probe = await fetch(modelUrl);
          const blobData = await probe.blob();
          const headBuf = await blobData.slice(0, 4).arrayBuffer();
          const bytes = new Uint8Array(headBuf);
          if (bytes[0] === 0x50 && bytes[1] === 0x4B && bytes[2] === 0x03 && bytes[3] === 0x04) {
            isZip = true;
          }
        } catch {
          // Probe fallback
        }

        if (isCancelled) return;

        if (ext === '3mf' || isZip) {
          const loader = new ThreeMFLoader();
          loader.load(
            modelUrl,
            (group) => {
              if (isCancelled) return;
              // 3MF files are Z-up; convert to Y-up
              group.rotation.set(-Math.PI / 2, 0, 0);
              group.updateMatrixWorld(true);

              let totalFaces = 0;
              let totalVertices = 0;

              group.traverse((child) => {
                if ((child as THREE.Mesh).isMesh) {
                  const m = child as THREE.Mesh;
                  m.castShadow = true;
                  m.receiveShadow = true;

                  if (!m.material) {
                    m.material = new THREE.MeshStandardMaterial({
                      color: 0x818cf8,
                      roughness: 0.35,
                      metalness: 0.25,
                    });
                  } else if (Array.isArray(m.material)) {
                    m.material.forEach((mat) => {
                      if (mat instanceof THREE.MeshStandardMaterial || mat instanceof THREE.MeshPhongMaterial) {
                        mat.roughness = mat.roughness ?? 0.35;
                        mat.metalness = mat.metalness ?? 0.25;
                      }
                    });
                  } else if (m.material instanceof THREE.MeshStandardMaterial || m.material instanceof THREE.MeshPhongMaterial) {
                    m.material.roughness = m.material.roughness ?? 0.35;
                    m.material.metalness = m.material.metalness ?? 0.25;
                  }

                  if (m.geometry) {
                    m.geometry.computeVertexNormals();
                    const pos = m.geometry.attributes.position;
                    if (pos) {
                      totalVertices += pos.count;
                      totalFaces += pos.count / 3;
                    }
                  }
                }
              });

              // Bounding box & centering
              const bbox = new THREE.Box3().setFromObject(group);
              const center = new THREE.Vector3();
              bbox.getCenter(center);
              const size = new THREE.Vector3();
              bbox.getSize(size);

              group.position.x -= center.x;
              group.position.y -= bbox.min.y;
              group.position.z -= center.z;

              const maxDim = Math.max(size.x, size.y, size.z) || 10;
              camera.position.set(maxDim * 1.5, maxDim * 1.3, maxDim * 1.8);
              camera.lookAt(0, size.y / 2, 0);
              controls.target.set(0, size.y / 2, 0);
              controls.update();

              loadedObject = group;
              scene.add(group);

              setStats({
                faces: Math.round(totalFaces),
                vertices: totalVertices,
                dimensions: `${size.x.toFixed(1)} x ${size.y.toFixed(1)} x ${size.z.toFixed(1)} mm`,
              });

              if (onSpecsComputed) {
                onSpecsComputed({
                  faces: Math.round(totalFaces),
                  vertices: totalVertices,
                  bbox_x: Math.round(size.x * 100) / 100,
                  bbox_y: Math.round(size.y * 100) / 100,
                  bbox_z: Math.round(size.z * 100) / 100,
                });
              }

              setLoading(false);
            },
            undefined,
            (err) => {
              console.error('Error loading 3MF model:', err);
              setError('Không thể tải hoặc hiển thị file 3MF này.');
              setLoading(false);
            }
          );
        } else if (ext === 'obj') {
          const loader = new OBJLoader();
          loader.load(
            modelUrl,
            (group) => {
              if (isCancelled) return;
              let totalFaces = 0;
              let totalVertices = 0;

              group.traverse((child) => {
                if ((child as THREE.Mesh).isMesh) {
                  const m = child as THREE.Mesh;
                  m.castShadow = true;
                  m.receiveShadow = true;

                  if (!m.material) {
                    m.material = new THREE.MeshStandardMaterial({
                      color: 0x818cf8,
                      roughness: 0.35,
                      metalness: 0.25,
                    });
                  }

                  if (m.geometry) {
                    m.geometry.computeVertexNormals();
                    const pos = m.geometry.attributes.position;
                    if (pos) {
                      totalVertices += pos.count;
                      totalFaces += pos.count / 3;
                    }
                  }
                }
              });

              const bbox = new THREE.Box3().setFromObject(group);
              const center = new THREE.Vector3();
              bbox.getCenter(center);
              const size = new THREE.Vector3();
              bbox.getSize(size);

              group.position.x -= center.x;
              group.position.y -= bbox.min.y;
              group.position.z -= center.z;

              const maxDim = Math.max(size.x, size.y, size.z) || 10;
              camera.position.set(maxDim * 1.5, maxDim * 1.3, maxDim * 1.8);
              camera.lookAt(0, size.y / 2, 0);
              controls.target.set(0, size.y / 2, 0);
              controls.update();

              loadedObject = group;
              scene.add(group);

              setStats({
                faces: Math.round(totalFaces),
                vertices: totalVertices,
                dimensions: `${size.x.toFixed(1)} x ${size.y.toFixed(1)} x ${size.z.toFixed(1)} mm`,
              });

              setLoading(false);
            },
            undefined,
            (err) => {
              console.error('Error loading OBJ model:', err);
              setError('Không thể tải hoặc hiển thị file OBJ này.');
              setLoading(false);
            }
          );
        } else {
          // Default: STLLoader
          const loader = new STLLoader();
          loader.load(
            modelUrl,
            (geometry) => {
              if (isCancelled) return;
              geometry.computeVertexNormals();
              geometry.computeBoundingBox();

              const bbox = geometry.boundingBox!;
              const center = new THREE.Vector3();
              bbox.getCenter(center);

              const size = new THREE.Vector3();
              bbox.getSize(size);
              geometry.translate(-center.x, -bbox.min.y, -center.z);

              const maxDim = Math.max(size.x, size.y, size.z) || 10;
              camera.position.set(maxDim * 1.5, maxDim * 1.3, maxDim * 1.8);
              camera.lookAt(0, size.y / 2, 0);
              controls.target.set(0, size.y / 2, 0);
              controls.update();

              const material = new THREE.MeshStandardMaterial({
                color: 0x818cf8,
                roughness: 0.35,
                metalness: 0.25,
              });

              const mesh = new THREE.Mesh(geometry, material);
              mesh.castShadow = true;
              mesh.receiveShadow = true;
              loadedObject = mesh;
              scene.add(mesh);

              const faces = geometry.attributes.position ? geometry.attributes.position.count / 3 : 0;
              const vertices = geometry.attributes.position ? geometry.attributes.position.count : 0;
              setStats({
                faces: Math.round(faces),
                vertices,
                dimensions: `${size.x.toFixed(1)} x ${size.y.toFixed(1)} x ${size.z.toFixed(1)} mm`,
              });

              if (onSpecsComputed) {
                onSpecsComputed({
                  faces: Math.round(faces),
                  vertices,
                  bbox_x: Math.round(size.x * 100) / 100,
                  bbox_y: Math.round(size.y * 100) / 100,
                  bbox_z: Math.round(size.z * 100) / 100,
                });
              }

              setLoading(false);
            },
            undefined,
            (err) => {
              console.error('Error loading STL in Three.js:', err);
              setError('Không thể tải hoặc hiển thị file 3D này.');
              setLoading(false);
            }
          );
        }
      } catch (e) {
        console.error('Error in loadModel:', e);
        setError('Lỗi khởi tạo xem mô hình 3D.');
        setLoading(false);
      }
    };

    loadModel();

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
      isCancelled = true;
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      controls.dispose();

      // Deep dispose entire scene to prevent WebGL memory leaks
      scene.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const m = child as THREE.Mesh;
          if (m.geometry) m.geometry.dispose();
          if (m.material) {
            if (Array.isArray(m.material)) {
              m.material.forEach((mat) => {
                if ('map' in mat && mat.map) mat.map.dispose();
                mat.dispose();
              });
            } else {
              if ('map' in m.material && (m.material as any).map) (m.material as any).map.dispose();
              m.material.dispose();
            }
          }
        }
      });

      renderer.dispose();
      renderer.forceContextLoss();

      if (container && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [modelUrl, fileExtension, filename]);

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

