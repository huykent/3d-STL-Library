'use client';

import { useEffect, useState, useCallback } from 'react';
import { getHistory, deleteModel } from '@/lib/api';
import { ModelCard, Model3D } from '@/components/ModelCard';
import { DownloadCloud } from 'lucide-react';

export default function HistoryPage() {
  const [models, setModels] = useState<Model3D[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchModels = useCallback(async () => {
    try {
      setLoading(true);
      const response = await getHistory();
      setModels(response.items);
      setTotal(response.total);
    } catch (error) {
      console.error('Failed to fetch history models:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleDelete = async (id: string) => {
    try {
      await deleteModel(id);
      setModels(prev => prev.filter(m => m.id !== id));
      setTotal(prev => prev - 1);
    } catch (error) {
      console.error('Failed to delete model:', error);
      alert('Failed to delete model.');
    }
  };

  return (
    <div className="flex flex-col w-full max-w-7xl mx-auto gap-6 pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
            <DownloadCloud className="w-8 h-8 text-blue-400" />
            Download History
          </h2>
          <p className="text-gray-400 mt-2">Models you have previously downloaded.</p>
        </div>
        <div className="text-gray-400 text-sm bg-white/5 px-4 py-2 rounded-full border border-white/10 backdrop-blur-md">
          {total} models downloaded
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6 mt-4">
        {models.map((model, i) => (
          <ModelCard key={`${model.id}-${i}`} model={model} onDelete={handleDelete} />
        ))}
      </div>

      {models.length === 0 && !loading && (
        <div className="flex flex-col items-center justify-center py-32 text-gray-500">
          <DownloadCloud className="w-16 h-16 text-gray-700 mb-4" />
          <p className="text-2xl font-medium text-gray-400 mb-2">No download history</p>
          <p>You haven't downloaded any models yet.</p>
        </div>
      )}
      
      {loading && (
        <div className="flex justify-center py-20">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      )}
    </div>
  );
}
