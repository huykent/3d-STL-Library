/* eslint-disable @next/next/no-img-element */
import Link from 'next/link';

export interface Model3D {
  id: string;
  original_filename: string;
  file_extension: string;
  file_size_bytes: number;
  vertex_count?: number;
  face_count?: number;
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
}

export function ModelCard({ model }: ModelCardProps) {
  const displayName = model.predicted_name || model.original_filename;
  
  return (
    <Link href={`/dashboard/models/${model.id}`}>
      <div className="bg-gray-800 rounded-lg overflow-hidden border border-gray-700 hover:border-blue-500 transition-colors shadow-sm hover:shadow-md cursor-pointer group flex flex-col h-full">
        {/* Thumbnail area */}
        <div className="aspect-video bg-gray-900 relative overflow-hidden flex items-center justify-center">
          {model.thumbnail_url ? (
            <img 
              src={model.thumbnail_url} 
              alt={displayName} 
              className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-300"
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
            <div className="absolute top-2 right-2 bg-black/60 backdrop-blur-sm text-xs px-2 py-1 rounded text-gray-200">
              {model.detail_level.replace('_', ' ')}
            </div>
          )}
        </div>

        {/* Content area */}
        <div className="p-4 flex flex-col flex-grow">
          <h3 className="text-white font-medium truncate mb-1" title={displayName}>
            {displayName}
          </h3>
          <p className="text-xs text-gray-400 truncate mb-3" title={model.original_filename}>
            {model.original_filename}
          </p>
          
          <div className="mt-auto flex items-center justify-between">
            <span className="text-xs font-medium bg-blue-900/40 text-blue-300 px-2 py-1 rounded">
              {model.ai_category || 'Uncategorized'}
            </span>
            <span className="text-xs text-gray-500">
              {model.face_count ? `${(model.face_count / 1000).toFixed(1)}k faces` : '??? faces'}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}
