import { useState, useEffect } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowUpDown, Check } from "lucide-react";
import { api } from "@/lib/api";

export interface FilterValues {
  search: string;
  detail_level: string;
  ai_category: string;
  ai_print_type: string;
  is_presupported?: string;
  studio?: string;
  sort_by: string;
}

interface SearchFilterProps {
  onFilterChange: (filters: FilterValues) => void;
}

export function SearchFilter({ onFilterChange }: SearchFilterProps) {
  const [filters, setFilters] = useState<FilterValues>({
    search: '',
    detail_level: '',
    ai_category: '',
    ai_print_type: '',
    is_presupported: '',
    studio: '',
    sort_by: 'newest',
  });

  const [studios, setStudios] = useState<string[]>([]);

  useEffect(() => {
    async function loadStudios() {
      try {
        const res = await api.get('/models/studios');
        if (Array.isArray(res.data)) {
          setStudios(res.data);
        }
      } catch (e) {
        console.error('Failed to load studios:', e);
      }
    }
    loadStudios();
  }, []);

  const handleChange = (key: keyof FilterValues, value: string) => {
    const newVal = (value === 'all' || value === '') ? '' : value;
    const newFilters = { ...filters, [key]: newVal };
    setFilters(newFilters);
    onFilterChange(newFilters);
  };

  return (
    <div className="flex flex-wrap gap-3 items-center w-full justify-between">
      <div className="flex flex-wrap gap-2.5 items-center">
        {/* Studio Filter */}
        {studios.length > 0 && (
          <Select value={filters.studio || 'all'} onValueChange={(val) => handleChange('studio', val)}>
            <SelectTrigger className="w-[140px] bg-purple-500/10 border-purple-500/30 text-purple-200 rounded-full h-9 text-xs">
              <SelectValue placeholder="All Studios" />
            </SelectTrigger>
            <SelectContent className="bg-gray-900 border-white/10 text-gray-200">
              <SelectItem value="all">Tất cả Studio</SelectItem>
              {studios.map((s) => (
                <SelectItem key={s} value={s}>🏷️ {s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Pre-supported Toggle */}
        <button
          onClick={() => {
            const nextVal = filters.is_presupported === 'true' ? '' : 'true';
            handleChange('is_presupported', nextVal);
          }}
          className={`h-9 px-3 rounded-full text-xs font-medium border flex items-center gap-1.5 transition-all ${
            filters.is_presupported === 'true'
              ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
              : 'bg-white/5 border-white/10 text-gray-400 hover:text-gray-200 hover:bg-white/10'
          }`}
        >
          <span>🟢 Pre-Supported</span>
          {filters.is_presupported === 'true' && <Check className="w-3.5 h-3.5 text-emerald-400" />}
        </button>

        <Select value={filters.detail_level || 'all'} onValueChange={(val) => handleChange('detail_level', val)}>
          <SelectTrigger className="w-[150px] bg-white/5 border-white/10 text-gray-200 rounded-full h-9 text-xs">
            <SelectValue placeholder="All Detail Levels" />
          </SelectTrigger>
          <SelectContent className="bg-gray-900 border-white/10 text-gray-200">
            <SelectItem value="all">All Detail Levels</SelectItem>
            <SelectItem value="low_poly">Low Poly (&lt;10k)</SelectItem>
            <SelectItem value="medium_poly">Medium Poly</SelectItem>
            <SelectItem value="high_poly">High Poly</SelectItem>
            <SelectItem value="resin_ready">Resin Ready (&gt;1M)</SelectItem>
          </SelectContent>
        </Select>

        <Select value={filters.ai_print_type || 'all'} onValueChange={(val) => handleChange('ai_print_type', val)}>
          <SelectTrigger className="w-[140px] bg-white/5 border-white/10 text-gray-200 rounded-full h-9 text-xs">
            <SelectValue placeholder="All Print Types" />
          </SelectTrigger>
          <SelectContent className="bg-gray-900 border-white/10 text-gray-200">
            <SelectItem value="all">All Print Types</SelectItem>
            <SelectItem value="FDM">FDM</SelectItem>
            <SelectItem value="Resin">Resin</SelectItem>
            <SelectItem value="Unknown">Unknown</SelectItem>
          </SelectContent>
        </Select>
        
        <Select value={filters.ai_category || 'all'} onValueChange={(val) => handleChange('ai_category', val)}>
          <SelectTrigger className="w-[140px] bg-white/5 border-white/10 text-gray-200 rounded-full h-9 text-xs">
            <SelectValue placeholder="All Categories" />
          </SelectTrigger>
          <SelectContent className="bg-gray-900 border-white/10 text-gray-200">
            <SelectItem value="all">All Categories</SelectItem>
            <SelectItem value="Functional">Functional</SelectItem>
            <SelectItem value="Mechanical">Mechanical</SelectItem>
            <SelectItem value="Figurine">Figurine</SelectItem>
            <SelectItem value="Prop">Prop</SelectItem>
            <SelectItem value="Miniature">Miniature</SelectItem>
            <SelectItem value="Terrain">Terrain</SelectItem>
            <SelectItem value="Jewelry">Jewelry</SelectItem>
            <SelectItem value="Art">Art</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-2">
        <Select value={filters.sort_by || 'newest'} onValueChange={(val) => handleChange('sort_by', val)}>
          <SelectTrigger className="w-[170px] bg-blue-600/10 border-blue-500/30 text-blue-300 rounded-full h-9 text-xs font-medium">
            <div className="flex items-center gap-1.5">
              <ArrowUpDown size={13} />
              <SelectValue placeholder="Sort By" />
            </div>
          </SelectTrigger>
          <SelectContent className="bg-gray-900 border-white/10 text-gray-200">
            <SelectItem value="newest">Newest First</SelectItem>
            <SelectItem value="faces_desc">Faces: High to Low</SelectItem>
            <SelectItem value="faces_asc">Faces: Low to High</SelectItem>
            <SelectItem value="name_asc">Name: A to Z</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

