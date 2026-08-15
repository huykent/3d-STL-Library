import Image from 'next/image';
import Link from 'next/link';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg';
  showText?: boolean;
}

export default function Logo({ size = 'md', showText = true }: LogoProps) {
  const dimensions = {
    sm: { box: 'w-8 h-8', img: 32, font: 'text-lg' },
    md: { box: 'w-10 h-10', img: 40, font: 'text-xl' },
    lg: { box: 'w-14 h-14', img: 56, font: 'text-3xl' },
  }[size];

  return (
    <Link href="/dashboard" className="flex items-center gap-3 group">
      <div className={`relative ${dimensions.box} rounded-xl overflow-hidden shadow-lg shadow-blue-500/20 border border-blue-500/30 transition-transform group-hover:scale-105 bg-gray-900`}>
        <Image
          src="/logo.png"
          alt="3D STL Library Logo"
          width={dimensions.img}
          height={dimensions.img}
          className="object-cover w-full h-full"
          priority
        />
      </div>
      {showText && (
        <div className="flex flex-col">
          <span className={`font-bold ${dimensions.font} bg-gradient-to-r from-blue-400 via-indigo-300 to-cyan-400 bg-clip-text text-transparent tracking-tight`}>
            3D STL Library
          </span>
          {size !== 'sm' && (
            <span className="text-[10px] uppercase tracking-widest text-blue-400/70 font-semibold -mt-1">
              Automated Hub
            </span>
          )}
        </div>
      )}
    </Link>
  );
}
