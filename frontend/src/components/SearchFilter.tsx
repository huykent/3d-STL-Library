import { useState } from 'react';

export interface FilterValues {
  search: string;
  detail_level: string;
  ai_category: string;
  ai_print_type: string;
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
  });

  const handleChange = (key: keyof FilterValues, value: string) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    onFilterChange(newFilters);
  };

  return (
    <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 mb-6 flex flex-col md:flex-row gap-4 items-center">
      <div className="flex-grow w-full md:w-auto">
        <input
          type="text"
          placeholder="Search models..."
          value={filters.search}
          onChange={(e) => handleChange('search', e.target.value)}
          className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      
      <div className="flex flex-wrap gap-4 w-full md:w-auto">
        <select
          value={filters.detail_level}
          onChange={(e) => handleChange('detail_level', e.target.value)}
          className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Detail Levels</option>
          <option value="low_poly">Low Poly (&lt;10k)</option>
          <option value="medium_poly">Medium Poly</option>
          <option value="high_poly">High Poly</option>
          <option value="resin_ready">Resin Ready (&gt;1M)</option>
        </select>

        <select
          value={filters.ai_print_type}
          onChange={(e) => handleChange('ai_print_type', e.target.value)}
          className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Print Types</option>
          <option value="FDM">FDM</option>
          <option value="Resin">Resin</option>
          <option value="Unknown">Unknown</option>
        </select>
        
        {/* We can hardcode some categories or fetch them, hardcoding for simplicity based on spec */}
        <select
          value={filters.ai_category}
          onChange={(e) => handleChange('ai_category', e.target.value)}
          className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Categories</option>
          <option value="Functional">Functional</option>
          <option value="Mechanical">Mechanical</option>
          <option value="Figurine">Figurine</option>
          <option value="Prop">Prop</option>
          <option value="Miniature">Miniature</option>
          <option value="Terrain">Terrain</option>
          <option value="Jewelry">Jewelry</option>
          <option value="Art">Art</option>
        </select>
      </div>
    </div>
  );
}
