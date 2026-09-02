'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, RotateCcw } from 'lucide-react';
import dynamic from 'next/dynamic';

// Load StlViewer with ssr:false — required for R3F Canvas in Next.js App Router
const StlViewer = dynamic(
  () => import('@/components/StlViewer').then((mod) => mod.StlViewer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex items-center justify-center text-gray-400 animate-pulse bg-gray-900">
        Đang tải engine 3D...
      </div>
    ),
  }
);

interface ModelPreviewModalProps {
  modelId: string;
  modelName: string;
  fileExtension?: string;
  filename?: string;
  onClose: () => void;
}

export function ModelPreviewModal({ modelId, modelName, fileExtension, filename, onClose }: ModelPreviewModalProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Ensure we only createPortal client-side
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    let url = '';
    const fetchBlob = async () => {
      try {
        const { api } = await import('@/lib/api');
        const res = await api.get(`/models/${modelId}/download`, { responseType: 'blob' });
        url = URL.createObjectURL(new Blob([res.data]));
        setBlobUrl(url);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchBlob();
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [modelId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  if (!mounted) return null;

  const modal = (
    <div
      className="fixed inset-0 z-[9999] bg-black/90 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl h-[80vh] bg-gray-900 rounded-2xl overflow-hidden border border-white/10 shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10 bg-black/30 flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <RotateCcw className="w-4 h-4 text-blue-400 flex-shrink-0 animate-spin" style={{ animationDuration: '4s' }} />
            <span className="text-white font-medium text-sm truncate">{modelName}</span>
            <span className="text-gray-500 text-xs hidden sm:block flex-shrink-0">• Kéo để xoay, cuộn để zoom</span>
          </div>
          <button
            onClick={onClose}
            className="ml-3 flex-shrink-0 bg-white/10 hover:bg-white/20 text-white rounded-full p-1.5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 3D Viewer — rendered in an isolated div to avoid React reconciler conflicts */}
        <div className="flex-1 relative overflow-hidden" id="stl-viewer-root">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900 z-10">
              <div className="text-center text-gray-400">
                <div className="text-4xl mb-3">⬡</div>
                <div className="animate-pulse">Đang tải file 3D...</div>
              </div>
            </div>
          )}
          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900 z-10">
              <div className="text-center text-gray-500">
                <div className="text-4xl mb-3">⚠️</div>
                <div>Không thể tải preview 3D</div>
              </div>
            </div>
          )}
          {blobUrl && !error && (
            <StlViewer modelUrl={blobUrl} fileExtension={fileExtension} filename={filename} />
          )}
        </div>
      </div>
    </div>
  );

  // Mount to document.body via portal to avoid R3F / React reconciler conflict
  return createPortal(modal, document.body);
}
