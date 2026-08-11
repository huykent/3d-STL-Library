/* eslint-disable @next/next/no-img-element */
import Link from 'next/link';
import { FiDownload, FiTrash2, FiEdit3 } from 'react-icons/fi';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export interface Model3D {
  id: string;
  original_filename: string;
  file_extension: string;
  file_size_bytes: number;
  vertex_count?: number;
  face_count?: number;
  part_count?: number;
  detail_level?: string;
  thumbnail_url?: string;
  predicted_name?: string;
  ai_category?: string;
  ai_print_type?: string;
  processing_status: string;
  tags?: { id: number; name: string; slug: string }[];
}

interface ModelCardProps {
  model: Model3D;
  onDelete?: (id: string) => void;
}

export function ModelCard({ model, onDelete }: ModelCardProps) {
  const displayName = model.predicted_name || model.original_filename;
  
  return (
    <Card className="overflow-hidden bg-white/5 border-white/10 hover:border-blue-500/50 hover:bg-white/10 backdrop-blur-md transition-all shadow-md group flex flex-col h-full relative p-0">
      
      {/* Hover Action Overlay */}
      <div className="absolute top-0 left-0 w-full h-full bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-10 flex items-center justify-center gap-4 backdrop-blur-[2px]">
        <Button 
          size="icon"
          onClick={(e) => { e.preventDefault(); /* trigger download */ }}
          className="bg-blue-600 hover:bg-blue-500 text-white rounded-full transition-transform hover:scale-110"
          title="Download"
        >
          <FiDownload className="w-4 h-4" />
        </Button>
        <Link href={`/dashboard/models/${model.id}`}>
          <Button 
            size="icon"
            variant="secondary"
            className="rounded-full shadow-lg transition-transform hover:scale-110" 
            title="View Details"
          >
            <FiEdit3 className="w-4 h-4" />
          </Button>
        </Link>
        <Button 
          size="icon"
          variant="destructive"
          onClick={(e) => { 
            e.preventDefault(); 
            if (onDelete && window.confirm('Are you sure you want to delete this model?')) {
              onDelete(model.id);
            }
          }}
          className="rounded-full transition-transform hover:scale-110"
          title="Delete"
        >
          <FiTrash2 className="w-4 h-4" />
        </Button>
      </div>

      <Link href={`/dashboard/models/${model.id}`} className="flex flex-col h-full z-0">
        {/* Thumbnail area */}
        <div className="aspect-video bg-black/40 relative overflow-hidden flex items-center justify-center shrink-0">
          {model.thumbnail_url ? (
            <img 
              src={model.thumbnail_url} 
              alt={displayName} 
              className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-500"
            />
          ) : (
            <div className="text-gray-500 flex flex-col items-center">
              <span className="text-sm font-medium">
                {model.processing_status === 'pending' || model.processing_status === 'processing' 
                  ? 'Processing...' 
                  : 'No Thumbnail'}
              </span>
            </div>
          )}
          {model.detail_level && (
            <div className="absolute top-3 right-3 flex flex-col gap-2">
              {model.part_count && model.part_count > 1 && (
                <Badge variant="secondary" className="bg-blue-600/80 text-white border-white/10 backdrop-blur-md">
                  {model.part_count} parts
                </Badge>
              )}
              <Badge variant="secondary" className="bg-black/60 text-gray-200 border-white/10 backdrop-blur-md">
                {model.detail_level.replace('_', ' ')}
              </Badge>
            </div>
          )}
        </div>

        {/* Content area */}
        <CardContent className="p-4 flex flex-col flex-grow">
          <h3 className="text-gray-100 font-semibold truncate mb-1" title={displayName}>
            {displayName}
          </h3>
          <p className="text-xs text-gray-500 truncate mb-4" title={model.original_filename}>
            {model.original_filename}
          </p>
          
          <div className="mt-auto flex items-center justify-between">
            <Badge variant="outline" className="bg-blue-500/10 border-blue-500/30 text-blue-400">
              {model.ai_category || 'Uncategorized'}
            </Badge>
            <span className="text-xs font-medium text-gray-400">
              {model.face_count ? `${(model.face_count / 1000).toFixed(1)}k faces` : '??? faces'}
            </span>
          </div>
        </CardContent>
      </Link>
    </Card>
  );
}
