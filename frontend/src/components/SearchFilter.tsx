import { useState } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowUpDown } from "lucide-react";

export interface FilterValues {
  search: string;
  detail_level: string;
  ai_category: string;
  ai_print_type: string;
  sort_by: string;
}

interface SearchFilterProps {
  onFilterChange: (filters: FilterValues) => void;
}

export function SearchFilter({ onFilterChange }: SearchFilterProps) {
  const [filters, setFilters] = useState<FilterValues>({
    search: '',
    detail_level: 'all',
    ai_category: 'all',
    ai_print_type: 'all',
    sort_by: 'newest',
  });

  const handleChange = (key: keyof FilterValues, value: string) => {
    const newVal = value === 'all' ? '' : value;
    const newFilters = { ...filters, [key]: newVal };
    setFilters(newFilters);
    onFilterChange(newFilters);
  };

  return (
    <div className="flex flex-wrap gap-3 items-center w-full justify-between">
      <div className="flex flex-wrap gap-3 items-center">
        <Select value={filters.detail_level || 'all'} onValueChange={(val) => handleChange('detail_level', val)}>
          <SelectTrigger className="w-[160px] bg-white/5 border-white/10 text-gray-200 rounded-full h-10">
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
          <SelectTrigger className="w-[150px] bg-white/5 border-white/10 text-gray-200 rounded-full h-10">
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
          <SelectTrigger className="w-[160px] bg-white/5 border-white/10 text-gray-200 rounded-full h-10">
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
          <SelectTrigger className="w-[180px] bg-blue-600/10 border-blue-500/30 text-blue-300 rounded-full h-10 font-medium">
            <div className="flex items-center gap-2">
              <ArrowUpDown size={14} />
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

