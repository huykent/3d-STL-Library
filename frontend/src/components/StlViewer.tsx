'use client';

import React, { Suspense, useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stage } from '@react-three/drei';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import * as THREE from 'three';

interface StlViewerProps {
  modelUrl: string;
}

function Model({ url }: { url: string }) {
  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);

  useEffect(() => {
    const loader = new STLLoader();
    loader.load(url, (geo) => {
      // Center the geometry
      geo.computeBoundingBox();
      geo.computeVertexNormals();
      const center = new THREE.Vector3();
      geo.boundingBox?.getCenter(center);
      geo.translate(-center.x, -center.y, -center.z);
      setGeometry(geo);
    });
  }, [url]);

  if (!geometry) {
    return null;
  }

  return (
    <mesh geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial color="#88aaff" roughness={0.4} metalness={0.2} />
    </mesh>
  );
}

export function StlViewer({ modelUrl }: StlViewerProps) {
  return (
    <div className="w-full h-full min-h-[400px] bg-gray-900 rounded-lg overflow-hidden border border-gray-700">
      <Canvas shadows camera={{ position: [0, -50, 50], fov: 45 }}>
        <Suspense fallback={null}>
          <Stage environment="city" intensity={0.5}>
            <Model url={modelUrl} />
          </Stage>
        </Suspense>
        <OrbitControls makeDefault autoRotate autoRotateSpeed={2.0} />
      </Canvas>
    </div>
  );
}
