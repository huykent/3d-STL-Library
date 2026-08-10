'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { StlViewer } from '@/components/StlViewer';
import { Model3D } from '@/components/ModelCard';

export default function ModelDetailPage() {
  const params = useParams();
  const router = useRouter();
  
  const [model, setModel] = useState<Model3D | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchModel = async () => {
      try {
        const response = await api.get(`/models/${params.id}`);
        setModel(response.data);
      } catch (err: unknown) {
        setError('Failed to load model details.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    if (params.id) {
      fetchModel();
    }
  }, [params.id]);

  const handleDownload = async () => {
    try {
      // In a real app we might fetch as blob to pass auth headers, 
      // then create an object URL. Since we're using Axios:
      const response = await api.get(`/models/${params.id}/download`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', model.original_filename || 'model.stl');
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed', err);
      alert('Failed to download model');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center text-white">
        <div className="animate-pulse text-xl">Loading model details...</div>
      </div>
    );
  }

  if (error || !model) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center text-white flex-col">
        <div className="text-red-500 mb-4 text-xl">{error || 'Model not found'}</div>
        <button 
          onClick={() => router.push('/dashboard')}
          className="text-blue-400 hover:underline"
        >
          Return to Dashboard
        </button>
      </div>
    );
  }

  const displayName = model.predicted_name || model.original_filename;
  // Construct the download URL for the StlViewer (which uses three.js loader and needs the raw URL).
  // Note: Since STLLoader uses a plain fetch, it doesn't automatically send the JWT. 
  // For a robust implementation we might need a custom loader or passing the blob directly.
  // For now we'll pass the URL, but the API requires auth!
  // To solve this, we can fetch the blob with Axios (which adds JWT) and create an Object URL.
  
  return (
    <div className="min-h-screen bg-gray-900 text-white pb-12">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 p-4 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto flex items-center gap-4">
          <button 
            onClick={() => router.push('/dashboard')}
            className="text-gray-400 hover:text-white transition-colors"
          >
            ← Back
          </button>
          <h1 className="text-xl font-bold truncate">
            {displayName}
          </h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-4 mt-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left Column: 3D Viewer */}
          <div className="lg:col-span-2 h-[600px]">
            <ModelViewerWrapper modelId={model.id} />
          </div>

          {/* Right Column: Details & Actions */}
          <div className="space-y-6">
            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-sm">
              <h2 className="text-lg font-semibold mb-4 border-b border-gray-700 pb-2">Actions</h2>
              <button 
                onClick={handleDownload}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-md transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                </svg>
                Download Model
              </button>
              <div className="mt-4 text-xs text-gray-400 text-center">
                Size: {(model.file_size_bytes / (1024 * 1024)).toFixed(2)} MB
              </div>
            </div>

            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-sm">
              <h2 className="text-lg font-semibold mb-4 border-b border-gray-700 pb-2">Model Details</h2>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-400">Original File</dt>
                  <dd className="font-medium truncate max-w-[150px]" title={model.original_filename}>
                    {model.original_filename}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-400">Status</dt>
                  <dd className="font-medium capitalize text-green-400">
                    {model.processing_status}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-400">Faces</dt>
                  <dd className="font-medium">
                    {model.face_count ? model.face_count.toLocaleString() : 'N/A'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-400">Detail Level</dt>
                  <dd className="font-medium capitalize">
                    {model.detail_level ? model.detail_level.replace('_', ' ') : 'N/A'}
                  </dd>
                </div>
                {model.bbox_x_mm && (
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Dimensions (mm)</dt>
                    <dd className="font-medium text-right">
                      {model.bbox_x_mm.toFixed(1)} x {model.bbox_y_mm.toFixed(1)} x {model.bbox_z_mm.toFixed(1)}
                    </dd>
                  </div>
                )}
              </dl>
            </div>

            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-sm">
              <h2 className="text-lg font-semibold mb-4 border-b border-gray-700 pb-2">AI Analysis</h2>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-400">Category</dt>
                  <dd className="font-medium bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded">
                    {model.ai_category || 'N/A'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-400">Print Type</dt>
                  <dd className="font-medium bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded">
                    {model.ai_print_type || 'N/A'}
                  </dd>
                </div>
              </dl>
              
              {model.tags && model.tags.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-sm text-gray-400 mb-2">Tags</h3>
                  <div className="flex flex-wrap gap-2">
                    {model.tags.map((tag: { id: number; name: string; slug: string }) => (
                      <span key={tag.id} className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded-full border border-gray-600">
                        {tag.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
          </div>
        </div>
      </main>
    </div>
  );
}

// Wrapper to fetch the model blob and pass object URL to StlViewer
// because three.js loader doesn't send our JWT auth header by default.
function ModelViewerWrapper({ modelId }: { modelId: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let url = '';
    const fetchBlob = async () => {
      try {
        const response = await api.get(`/models/${modelId}/download`, {
          responseType: 'blob'
        });
        url = URL.createObjectURL(new Blob([response.data]));
        setBlobUrl(url);
      } catch (err) {
        console.error('Failed to load 3D model blob', err);
        setError(true);
      }
    };
    fetchBlob();

    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [modelId]);

  if (error) {
    return (
      <div className="w-full h-full min-h-[400px] bg-gray-900 rounded-lg flex items-center justify-center border border-gray-700">
        <span className="text-gray-500">Failed to load 3D preview</span>
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className="w-full h-full min-h-[400px] bg-gray-900 rounded-lg flex items-center justify-center border border-gray-700">
        <span className="animate-pulse text-gray-400">Loading 3D data...</span>
      </div>
    );
  }

  return <StlViewer modelUrl={blobUrl} />;
}
