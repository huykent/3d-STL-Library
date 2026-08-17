'use client';

import { useEffect, useState } from 'react';
import { X, RotateCcw } from 'lucide-react';
import dynamic from 'next/dynamic';

const StlViewer = dynamic(
  () => import('@/components/StlViewer').then((mod) => mod.StlViewer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex items-center justify-center text-gray-400 animate-pulse">
        Đang tải engine 3D...
      </div>
    ),
  }
);

interface ModelPreviewModalProps {
  modelId: string;
  modelName: string;
  onClose: () => void;
}

export function ModelPreviewModal({ modelId, modelName, onClose }: ModelPreviewModalProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

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

  return (
    <div
      className="fixed inset-0 z-[999] bg-black/90 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl h-[80vh] bg-gray-900 rounded-2xl overflow-hidden border border-white/10 shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10 bg-black/30">
          <div className="flex items-center gap-2">
            <RotateCcw className="w-4 h-4 text-blue-400 animate-spin" style={{ animationDuration: '4s' }} />
            <span className="text-white font-medium text-sm truncate max-w-xs">{modelName}</span>
            <span className="text-gray-500 text-xs">• Kéo để xoay, cuộn để zoom</span>
          </div>
          <button
            onClick={onClose}
            className="bg-white/10 hover:bg-white/20 text-white rounded-full p-1.5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Viewer */}
        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center text-gray-400 animate-pulse bg-gray-900">
              <div className="text-center">
                <div className="text-4xl mb-3">⬡</div>
                <div>Đang tải file 3D...</div>
              </div>
            </div>
          )}
          {error && (
            <div className="absolute inset-0 flex items-center justify-center text-gray-500 bg-gray-900">
              <div className="text-center">
                <div className="text-4xl mb-3">⚠️</div>
                <div>Không thể tải preview 3D</div>
              </div>
            </div>
          )}
          {blobUrl && <StlViewer modelUrl={blobUrl} />}
        </div>
      </div>
    </div>
  );
}
