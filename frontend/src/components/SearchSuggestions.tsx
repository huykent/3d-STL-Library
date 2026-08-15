'use client';

import Image from 'next/image';
import Link from 'next/link';
import { Box, Sparkles } from 'lucide-react';

export interface SuggestionItem {
  id: string;
  name: str;
  ai_category: string;
  thumbnail_url: string | null;
}

interface SearchSuggestionsProps {
  suggestions: SuggestionItem[];
  loading: boolean;
  onSelect: () => void;
}

export function SearchSuggestions({ suggestions, loading, onSelect }: SearchSuggestionsProps) {
  if (loading) {
    return (
      <div className="absolute left-0 right-0 top-full mt-2 bg-[#0d0d15]/95 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-xl p-4 z-50 animate-in fade-in slide-in-from-top-2 duration-200">
        <div className="flex items-center justify-center gap-2 text-gray-400 py-3">
          <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-medium">Searching models...</span>
        </div>
      </div>
    );
  }

  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div className="absolute left-0 right-0 top-full mt-2 bg-[#0d0d15]/95 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-xl p-2 z-50 animate-in fade-in slide-in-from-top-2 duration-200 overflow-hidden">
      <div className="px-3 py-1.5 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-blue-400 border-b border-white/5 mb-1">
        <span className="flex items-center gap-1.5">
          <Sparkles size={12} />
          Smart Suggestions
        </span>
        <span className="text-gray-500 font-normal">{suggestions.length} results</span>
      </div>

      <div className="space-y-1">
        {suggestions.map((item) => (
          <Link
            key={item.id}
            href={`/dashboard?q=${encodeURIComponent(item.name)}`}
            onClick={onSelect}
            className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/10 transition-colors group"
          >
            <div className="w-9 h-9 rounded-lg bg-black/40 border border-white/10 flex items-center justify-center overflow-hidden shrink-0 group-hover:border-blue-500/50 transition-colors">
              {item.thumbnail_url ? (
                <img
                  src={item.thumbnail_url}
                  alt={item.name}
                  className="w-full h-full object-cover"
                />
              ) : (
                <Box size={18} className="text-gray-500 group-hover:text-blue-400 transition-colors" />
              )}
            </div>

            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-sm font-medium text-gray-200 group-hover:text-white truncate">
                {item.name}
              </span>
              <span className="text-[11px] text-gray-500 group-hover:text-gray-400">
                {item.ai_category}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
