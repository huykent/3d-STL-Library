'use client';

import { useEffect, useState, useCallback } from 'react';
import { getFavorites, deleteModel } from '@/lib/api';
import { ModelCard, Model3D } from '@/components/ModelCard';
import { Heart } from 'lucide-react';

export default function FavoritesPage() {
  const [models, setModels] = useState<Model3D[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchModels = useCallback(async () => {
    try {
      setLoading(true);
      const response = await getFavorites();
      setModels(response.items);
      setTotal(response.total);
    } catch (error) {
      console.error('Failed to fetch favorite models:', error);
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
            <Heart className="w-8 h-8 text-pink-500 fill-pink-500" />
            My Favorites
          </h2>
          <p className="text-gray-400 mt-2">Models you have saved for quick access.</p>
        </div>
        <div className="text-gray-400 text-sm bg-white/5 px-4 py-2 rounded-full border border-white/10 backdrop-blur-md">
          {total} models saved
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6 mt-4">
        {models.map((model) => (
          <ModelCard key={model.id} model={model} onDelete={handleDelete} />
        ))}
      </div>

      {models.length === 0 && !loading && (
        <div className="flex flex-col items-center justify-center py-32 text-gray-500">
          <Heart className="w-16 h-16 text-gray-700 mb-4" />
          <p className="text-2xl font-medium text-gray-400 mb-2">No favorites yet</p>
          <p>You haven't added any models to your favorites.</p>
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
