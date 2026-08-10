'use client';

import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { ModelCard, Model3D } from '@/components/ModelCard';
import { SearchFilter, FilterValues } from '@/components/SearchFilter';
import { useAuth } from '@/components/AuthProvider';

export default function DashboardPage() {
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

  const { logout } = useAuth();

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
    // Debounce search slightly
    const timer = setTimeout(() => {
      setPage(1);
      fetchModels(filters, 1, false);
    }, 300);
    return () => clearTimeout(timer);
  }, [filters, fetchModels]);

  const loadMore = () => {
    if (!loading && hasNext) {
      const nextPage = page + 1;
      setPage(nextPage);
      fetchModels(filters, nextPage, true);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 p-4 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-cyan-300">
            3D STL Library
          </h1>
          <button 
            onClick={logout}
            className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto p-4 py-8">
        <SearchFilter onFilterChange={setFilters} />
        
        <div className="mb-4 text-gray-400 text-sm">
          Found {total} models
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {models.map(model => (
            <ModelCard key={model.id} model={model} />
          ))}
        </div>

        {models.length === 0 && !loading && (
          <div className="text-center py-20 text-gray-500">
            <p className="text-xl">No models found</p>
            <p className="mt-2">Try adjusting your filters</p>
          </div>
        )}

        {hasNext && (
          <div className="mt-12 flex justify-center">
            <button
              onClick={loadMore}
              disabled={loading}
              className="bg-gray-800 hover:bg-gray-700 border border-gray-600 text-white font-medium py-2 px-6 rounded-full transition-colors disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Load More'}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
