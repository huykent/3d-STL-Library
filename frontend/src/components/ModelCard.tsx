/* eslint-disable @next/next/no-img-element */
'use client';
import { useState } from 'react';
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
  image_urls?: string[];
  predicted_name?: string;
  ai_category?: string;
  ai_print_type?: string;
  processing_status: string;
  processing_logs?: any[];
  tags?: { id: number; name: string; slug: string }[];
}

interface ModelCardProps {
  model: Model3D;
  onDelete?: (id: string) => void;
}

// ── Image Carousel sub-component ──────────────────────────────────────────────
interface CarouselProps {
  images: string[];
  alt: string;
  processingStatus: string;
  detailLevel?: string;
  partCount?: number;
}

function ImageCarousel({ images, alt, processingStatus, detailLevel, partCount }: CarouselProps) {
  const [idx, setIdx] = useState(0);

  const prev = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIdx((i) => (i - 1 + images.length) % images.length);
  };

  const next = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIdx((i) => (i + 1) % images.length);
  };

  const goTo = (e: React.MouseEvent, n: number) => {
    e.preventDefault();
    e.stopPropagation();
    setIdx(n);
  };

  return (
    <div className="aspect-video bg-black/40 relative overflow-hidden flex items-center justify-center shrink-0">
      {images.length > 0 ? (
        <>
          <img
            src={images[idx]}
            alt={`${alt} — ảnh ${idx + 1}/${images.length}`}
            className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-500"
          />

          {/* Prev / Next — only when multiple images */}
          {images.length > 1 && (
            <>
              <button
                onClick={prev}
                className="absolute left-1 top-1/2 -translate-y-1/2 z-20 bg-black/50 hover:bg-black/80 text-white rounded-full w-7 h-7 flex items-center justify-center text-lg leading-none opacity-0 group-hover:opacity-100 transition-opacity"
                title="Ảnh trước"
              >
                ‹
              </button>
              <button
                onClick={next}
                className="absolute right-1 top-1/2 -translate-y-1/2 z-20 bg-black/50 hover:bg-black/80 text-white rounded-full w-7 h-7 flex items-center justify-center text-lg leading-none opacity-0 group-hover:opacity-100 transition-opacity"
                title="Ảnh tiếp"
              >
                ›
              </button>

              {/* Dot indicators */}
              <div className="absolute bottom-2 left-0 right-0 flex justify-center gap-1 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                {images.map((_, i) => (
                  <button
                    key={i}
                    onClick={(e) => goTo(e, i)}
                    className={`w-1.5 h-1.5 rounded-full transition-all ${
                      i === idx ? 'bg-white scale-125' : 'bg-white/40 hover:bg-white/70'
                    }`}
                  />
                ))}
              </div>

              {/* Counter badge */}
              <div className="absolute top-2 left-2 z-20 bg-black/60 text-white text-[10px] font-medium px-1.5 py-0.5 rounded-full backdrop-blur-sm pointer-events-none">
                {idx + 1}/{images.length}
              </div>
            </>
          )}
        </>
      ) : (
        <div className="text-gray-500 flex flex-col items-center">
          <span className="text-sm font-medium">
            {processingStatus === 'pending' || processingStatus === 'processing'
              ? 'Processing...'
              : 'No Thumbnail'}
          </span>
        </div>
      )}

      {/* Detail level / part count badges */}
      {detailLevel && (
        <div className="absolute top-3 right-3 flex flex-col gap-2 z-10">
          {partCount && partCount > 1 && (
            <Badge variant="secondary" className="bg-blue-600/80 text-white border-white/10 backdrop-blur-md">
              {partCount} parts
            </Badge>
          )}
          <Badge variant="secondary" className="bg-black/60 text-gray-200 border-white/10 backdrop-blur-md">
            {detailLevel.replace('_', ' ')}
          </Badge>
        </div>
      )}
    </div>
  );
}

// ── Main ModelCard component ───────────────────────────────────────────────────
export function ModelCard({ model, onDelete }: ModelCardProps) {
  const displayName = model.predicted_name || model.original_filename;

  // Build full image list: image_urls first, then thumbnail as last resort
  const allImages: string[] = [];
  if (model.image_urls?.length) {
    allImages.push(...model.image_urls);
  }
  if (model.thumbnail_url && !allImages.includes(model.thumbnail_url)) {
    allImages.push(model.thumbnail_url);
  }

  return (
    <Card className="overflow-hidden bg-white/5 border-white/10 hover:border-blue-500/50 hover:bg-white/10 backdrop-blur-md transition-all shadow-md group flex flex-col h-full relative p-0">

      {/* Hover Action Overlay */}
      <div className="absolute top-0 left-0 w-full h-full bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-10 flex items-center justify-center gap-4 backdrop-blur-[2px]">
        <Button
          size="icon"
          onClick={async (e) => {
            e.preventDefault();
            try {
              const { recordHistory } = await import('@/lib/api');
              await recordHistory(model.id);
            } catch (err) {
              console.error(err);
            }
            window.open(`/api/models/${model.id}/download`, '_blank');
          }}
          className="bg-blue-600 hover:bg-blue-500 text-white rounded-full transition-transform hover:scale-110"
          title="Download"
        >
          <FiDownload className="w-4 h-4" />
        </Button>

        <Button
          size="icon"
          variant="secondary"
          onClick={async (e) => {
            e.preventDefault();
            try {
              const { addFavorite } = await import('@/lib/api');
              const res = await addFavorite(model.id);
              if (res.status === 'added') alert('Added to favorites!');
              else if (res.status === 'already_exists') alert('Already in favorites!');
            } catch (err) {
              console.error(err);
            }
          }}
          className="rounded-full shadow-lg transition-transform hover:scale-110 text-pink-500 hover:text-pink-400"
          title="Add to Favorites"
        >
          <svg stroke="currentColor" fill="currentColor" strokeWidth="0" viewBox="0 0 512 512" height="1em" width="1em" xmlns="http://www.w3.org/2000/svg">
            <path d="M462.3 62.6C407.5 15.9 326 24.3 275.7 76.2L256 96.5l-19.7-20.3C186.1 24.3 104.5 15.9 49.7 62.6c-62.8 53.6-66.1 149.8-9.9 207.9l193.5 199.8c12.5 12.9 32.8 12.9 45.3 0l193.5-199.8c56.3-58.1 53-154.3-9.8-207.9z" />
          </svg>
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
        {/* Image Carousel */}
        <ImageCarousel
          images={allImages}
          alt={displayName}
          processingStatus={model.processing_status}
          detailLevel={model.detail_level}
          partCount={model.part_count}
        />

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
