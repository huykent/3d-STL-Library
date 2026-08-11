'use client';

import { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { api, deleteModel } from '@/lib/api';
import { ModelCard, Model3D } from '@/components/ModelCard';
import { SearchFilter, FilterValues } from '@/components/SearchFilter';
import UploadModal from '@/components/UploadModal';
import { UploadCloud } from 'lucide-react';

export default function DashboardPage() {
  const searchParams = useSearchParams();
  const search = searchParams.get('q') || '';

  const [models, setModels] = useState<Model3D[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [filters, setFilters] = useState<FilterValues>({
    search: '',
    detail_level: '',
    ai_category: '',
    ai_print_type: '',
  });
  const [showUploadModal, setShowUploadModal] = useState(false);

  const fetchModels = useCallback(async (currentFilters: FilterValues, currentPage: number, append: boolean = false) => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.append('page', currentPage.toString());
      params.append('page_size', '24');
      
      if (currentFilters.search) params.append('search', currentFilters.search);
      if (currentFilters.detail_level) params.append('detail_level', currentFilters.detail_level);
      if (currentFilters.ai_category) params.append('ai_category', currentFilters.ai_category);
      if (currentFilters.ai_print_type) params.append('ai_print_type', currentFilters.ai_print_type);

      const response = await api.get(`/models?${params.toString()}`);
      
      if (append) {
        setModels(prev => [...prev, ...response.data.items]);
      } else {
        setModels(response.data.items);
      }
      
      setTotal(response.data.total);
      setHasNext(response.data.has_next);
    } catch (error) {
      console.error('Failed to fetch models:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load and filter change
  useEffect(() => {
    const currentFilters = { ...filters, search };
    const timer = setTimeout(() => {
      setPage(1);
      fetchModels(currentFilters, 1, false);
    }, 300);
    return () => clearTimeout(timer);
  }, [filters, search, fetchModels]);

  const loadMore = () => {
    if (!loading && hasNext) {
      const nextPage = page + 1;
      setPage(nextPage);
      fetchModels(filters, nextPage, true);
    }
  };

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
        <h2 className="text-3xl font-bold text-white tracking-tight">Gallery</h2>
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setShowUploadModal(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-full transition-colors"
          >
            <UploadCloud size={18} />
            <span>Upload Model</span>
          </button>
          <div className="text-gray-400 text-sm bg-white/5 px-4 py-2 rounded-full border border-white/10 backdrop-blur-md">
            Found {total} models
          </div>
        </div>
      </div>

      <SearchFilter onFilterChange={setFilters} />

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6 mt-4">
        {models.map((model) => (
          <ModelCard key={model.id} model={model} onDelete={handleDelete} />
        ))}
      </div>

      {models.length === 0 && !loading && (
        <div className="flex flex-col items-center justify-center py-32 text-gray-500">
          <p className="text-2xl font-medium text-gray-400 mb-2">No models found</p>
          <p>Try adjusting your filters or search terms.</p>
        </div>
      )}

      {hasNext && (
        <div className="mt-12 flex justify-center pb-8">
          <button
            onClick={loadMore}
            disabled={loading}
            className="bg-white/10 hover:bg-white/20 border border-white/20 text-white font-medium py-3 px-8 rounded-full transition-all disabled:opacity-50 hover:shadow-[0_0_20px_rgba(255,255,255,0.1)]"
          >
            {loading ? 'Loading...' : 'Load More Models'}
          </button>
        </div>
      )}

      {showUploadModal && (
        <UploadModal onClose={() => setShowUploadModal(false)} />
      )}
    </div>
  );
}
