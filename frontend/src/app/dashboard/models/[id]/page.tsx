'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import dynamic from 'next/dynamic';
const StlViewer = dynamic(() => import('@/components/StlViewer').then(mod => mod.StlViewer), { 
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[400px] bg-gray-900 rounded-lg flex items-center justify-center border border-gray-700">
      <span className="animate-pulse text-gray-400">Loading 3D viewer engine...</span>
    </div>
  )
});
import { Model3D } from '@/components/ModelCard';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, Download, Edit2, Save } from "lucide-react";

export default function ModelDetailPage() {
  const params = useParams();
  const router = useRouter();
  
  const [model, setModel] = useState<Model3D | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<any>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    const fetchModel = async () => {
      try {
        const response = await api.get(`/models/${params.id}`);
        setModel(response.data);
        if (!isEditing) {
          setEditData({
            predicted_name: response.data.predicted_name || response.data.original_filename,
            ai_category: response.data.ai_category || '',
            ai_print_type: response.data.ai_print_type || '',
            keywords: response.data.tags?.map((t: any) => t.name).join(', ') || ''
          });
        }
        
        // Stop polling if completed or failed
        if (response.data.processing_status === 'completed' || response.data.processing_status === 'failed') {
          clearInterval(interval);
        }
      } catch (err: unknown) {
        if (!model) setError('Failed to load model details.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    if (params.id) {
      fetchModel();
      // Start polling every 3 seconds for live updates
      interval = setInterval(fetchModel, 3000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [params.id, isEditing]);

  const handleDownload = async () => {
    if (!model) return;
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

  const handleSave = async () => {
    if (!model) return;
    setSaving(true);
    try {
      const payload = {
        ...editData,
        keywords: editData.keywords.split(',').map((k: string) => k.trim()).filter(Boolean)
      };
      const response = await api.put(`/models/${params.id}`, payload);
      setModel(response.data);
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to update model', err);
      alert('Failed to update model');
    } finally {
      setSaving(false);
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
  
  return (
    <div className="min-h-screen bg-gray-900 text-white pb-12">
      {/* Header */}
      <header className="bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b border-white/10 p-4 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Button 
              variant="ghost"
              size="sm"
              onClick={() => router.push('/dashboard')}
              className="text-gray-400 hover:text-white"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <h1 className="text-xl font-bold truncate tracking-tight text-gray-100">
              {displayName}
            </h1>
          </div>
          <Button
            onClick={() => isEditing ? handleSave() : setIsEditing(true)}
            disabled={saving}
            variant={isEditing ? "default" : "secondary"}
          >
            {saving ? 'Saving...' : (
              isEditing ? <><Save className="w-4 h-4 mr-2"/> Save Changes</> : <><Edit2 className="w-4 h-4 mr-2"/> Edit Model</>
            )}
          </Button>
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
            <Card className="bg-[#1c2128] border-white/10">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg text-white">Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button 
                  onClick={handleDownload}
                  className="w-full bg-blue-600 hover:bg-blue-700"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download Model
                </Button>
                <div className="text-xs text-gray-400 text-center">
                  Size: {(model.file_size_bytes / (1024 * 1024)).toFixed(2)} MB
                </div>
              </CardContent>
            </Card>

            <Card className="bg-[#1c2128] border-white/10">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg text-white">Model Details</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="space-y-4 text-sm">
                  <div className="flex justify-between items-center">
                    <dt className="text-gray-400">Original File</dt>
                    <dd className="font-medium truncate max-w-[150px] text-gray-200" title={model.original_filename}>
                      {model.original_filename}
                    </dd>
                  </div>
                  <div className="flex justify-between items-center">
                    <dt className="text-gray-400">Status</dt>
                    <dd>
                      <Badge variant="outline" className="text-green-400 border-green-400/30 bg-green-400/10 capitalize">
                        {model.processing_status}
                      </Badge>
                    </dd>
                  </div>
                  <div className="flex justify-between items-center">
                    <dt className="text-gray-400">Faces</dt>
                    <dd className="font-medium text-gray-200">
                      {model.face_count ? model.face_count.toLocaleString() : 'N/A'}
                    </dd>
                  </div>
                  <div className="flex justify-between items-center">
                    <dt className="text-gray-400">Detail Level</dt>
                    <dd className="font-medium capitalize text-gray-200">
                      {model.detail_level ? model.detail_level.replace('_', ' ') : 'N/A'}
                    </dd>
                  </div>
                  {model.part_count && model.part_count > 1 && (
                    <div className="flex justify-between items-center">
                      <dt className="text-gray-400">Parts Inside</dt>
                      <dd className="font-medium text-gray-200">
                        {model.part_count} files
                      </dd>
                    </div>
                  )}
                  {model.bbox_x_mm && (
                    <div className="flex justify-between items-center">
                      <dt className="text-gray-400">Dimensions (mm)</dt>
                      <dd className="font-medium text-right text-gray-200">
                        {model.bbox_x_mm.toFixed(1)} x {model.bbox_y_mm.toFixed(1)} x {model.bbox_z_mm.toFixed(1)}
                      </dd>
                    </div>
                  )}
                </dl>
              </CardContent>
            </Card>

            <Card className="bg-[#1c2128] border-white/10">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg text-white">AI Analysis</CardTitle>
              </CardHeader>
              <CardContent>
              {isEditing ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-300">Title</label>
                    <Input 
                      className="bg-[#0d1117] border-white/10 text-white"
                      value={editData.predicted_name}
                      onChange={e => setEditData({...editData, predicted_name: e.target.value})}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-300">Category</label>
                    <Input 
                      className="bg-[#0d1117] border-white/10 text-white"
                      value={editData.ai_category}
                      onChange={e => setEditData({...editData, ai_category: e.target.value})}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-300">Print Type</label>
                    <Select 
                      value={editData.ai_print_type || "Unknown"}
                      onValueChange={val => setEditData({...editData, ai_print_type: val})}
                    >
                      <SelectTrigger className="bg-[#0d1117] border-white/10 text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-gray-900 border-white/10 text-white">
                        <SelectItem value="FDM">FDM</SelectItem>
                        <SelectItem value="Resin">Resin</SelectItem>
                        <SelectItem value="Unknown">Unknown</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-300">Tags (comma separated)</label>
                    <Input 
                      className="bg-[#0d1117] border-white/10 text-white"
                      value={editData.keywords}
                      onChange={e => setEditData({...editData, keywords: e.target.value})}
                    />
                  </div>
                </div>
              ) : (
                <>
                  <dl className="space-y-4 text-sm">
                    <div className="flex justify-between items-center">
                      <dt className="text-gray-400">Category</dt>
                      <dd>
                        <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/30">
                          {model.ai_category || 'N/A'}
                        </Badge>
                      </dd>
                    </div>
                    <div className="flex justify-between items-center">
                      <dt className="text-gray-400">Print Type</dt>
                      <dd>
                        <Badge variant="outline" className="bg-purple-500/10 text-purple-400 border-purple-500/30">
                          {model.ai_print_type || 'N/A'}
                        </Badge>
                      </dd>
                    </div>
                  </dl>
                  
                  {model.tags && model.tags.length > 0 && (
                    <div className="mt-6">
                      <h3 className="text-sm font-medium text-gray-400 mb-3">Tags</h3>
                      <div className="flex flex-wrap gap-2">
                        {model.tags.map((tag: { id: number; name: string; slug: string }) => (
                          <Badge key={tag.id} variant="secondary" className="bg-white/5 hover:bg-white/10 text-gray-300">
                            {tag.name}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
              </CardContent>
            </Card>

            {model.processing_logs && model.processing_logs.length > 0 && (
              <Card className="bg-[#1c2128] border-white/10">
                <CardHeader className="pb-4">
                  <CardTitle className="text-lg text-white">Tiến trình xử lý (Logs)</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                    {model.processing_logs.map((log, idx) => (
                      <div key={idx} className="flex gap-3 text-sm">
                        <div className="flex flex-col items-center mt-1">
                          <div className={`w-2 h-2 rounded-full ${idx === model.processing_logs!.length - 1 && model.processing_status === 'processing' ? 'bg-blue-400 animate-pulse' : 'bg-gray-500'}`} />
                          {idx < model.processing_logs!.length - 1 && <div className="w-px h-full bg-gray-700 my-1" />}
                        </div>
                        <div className="pb-4">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-gray-300">{log.step}</span>
                            <span className="text-xs text-gray-500">{new Date(log.time).toLocaleTimeString()}</span>
                          </div>
                          <p className="text-gray-400 mt-1">{log.message}</p>
                          {log.path && (
                            <code className="text-xs bg-black/30 text-gray-500 px-2 py-1 rounded mt-2 block break-all">
                              {log.path}
                            </code>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
            
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
