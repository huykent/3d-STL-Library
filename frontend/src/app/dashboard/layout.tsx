"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FiGrid, FiSettings, FiTerminal, FiLogOut, FiUploadCloud, FiSearch, FiLayers } from "react-icons/fi";

import { Menu } from "lucide-react";
import { useState, useCallback, Suspense } from "react";
import UploadModal from "@/components/UploadModal";
import { useAuth } from "@/components/AuthProvider";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

import Logo from "@/components/Logo";
import { SearchSuggestions, SuggestionItem } from "@/components/SearchSuggestions";

import { api } from "@/lib/api";
import { X } from "lucide-react";
import { useRef, useEffect } from "react";

function HeaderSearch() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [searchTerm, setSearchTerm] = useState(searchParams.get("q") || "");
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSearchTerm(searchParams.get("q") || "");
  }, [searchParams]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!searchTerm || searchTerm.trim().length < 2) {
      setSuggestions([]);
      setLoadingSuggestions(false);
      return;
    }

    setLoadingSuggestions(true);
    const timer = setTimeout(async () => {
      try {
        const response = await api.get(`/models/suggestions?q=${encodeURIComponent(searchTerm)}`);
        setSuggestions(response.data.models || []);
        setShowSuggestions(true);
      } catch (err) {
        console.error("Failed to fetch search suggestions", err);
      } finally {
        setLoadingSuggestions(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchTerm(val);
    if (!val) {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("q");
      router.push(`/dashboard?${params.toString()}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      setShowSuggestions(false);
      const params = new URLSearchParams(searchParams.toString());
      if (searchTerm) {
        params.set("q", searchTerm);
      } else {
        params.delete("q");
      }
      router.push(`/dashboard?${params.toString()}`);
    }
  };

  const clearSearch = () => {
    setSearchTerm("");
    setShowSuggestions(false);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("q");
    router.push(`/dashboard?${params.toString()}`);
  };

  return (
    <div ref={containerRef} className="relative w-full max-w-xl group">
      <FiSearch className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-blue-400 transition-colors z-10" />
      <input
        type="text"
        placeholder="Smart Search (e.g. 'Goku resin high poly', 'Star Wars')..."
        value={searchTerm}
        onChange={handleSearchChange}
        onKeyDown={handleKeyDown}
        onFocus={() => {
          if (suggestions.length > 0) setShowSuggestions(true);
        }}
        className="w-full bg-black/20 border border-white/10 rounded-full py-2 md:py-2.5 pl-10 md:pl-12 pr-10 text-sm focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all placeholder-gray-500 text-white"
      />
      {searchTerm && (
        <button
          onClick={clearSearch}
          className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors z-10"
        >
          <X size={16} />
        </button>
      )}

      {showSuggestions && (
        <SearchSuggestions
          suggestions={suggestions}
          loading={loadingSuggestions}
          onSelect={() => setShowSuggestions(false)}
        />
      )}
    </div>
  );
}


export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const router = useRouter();
  const [showUpload, setShowUpload] = useState(false);

  const baseNavItems = [
    { name: "Gallery", href: "/dashboard", icon: FiGrid },
    { name: "Active Queue", href: "/dashboard/queue", icon: FiLayers },
  ];



  const userNavItems = [
    { name: "My Profile", href: "/dashboard/profile", icon: FiSettings },
    { name: "Favorites", href: "/dashboard/favorites", icon: FiGrid },
    { name: "Download History", href: "/dashboard/history", icon: FiTerminal },
  ];

  const adminNavItems = [
    { name: "User Management", href: "/dashboard/users", icon: FiGrid },
    { name: "System Settings", href: "/dashboard/settings", icon: FiSettings },
    { name: "System Logs", href: "/dashboard/logs", icon: FiTerminal },
  ];

  const renderNavGroup = (title: string, items: {name: string, href: string, icon: any}[]) => (
    <div className="mb-6">
      <h3 className="px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{title}</h3>
      <div className="space-y-1">
        {items.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all duration-300 ${
                isActive
                  ? "bg-gradient-to-r from-blue-600/30 to-purple-600/30 text-white shadow-[0_0_15px_rgba(59,130,246,0.3)] border border-white/10"
                  : "text-gray-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <item.icon className={`w-5 h-5 ${isActive ? "text-blue-400" : ""}`} />
              <span className="font-medium text-sm">{item.name}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );

  const SidebarContent = () => (

    <>
      <div className="p-6">
        <Logo size="md" />
      </div>



      <nav className="flex-1 px-4 py-4 overflow-y-auto">
        {renderNavGroup("Discover", baseNavItems)}
        {renderNavGroup("My Account", userNavItems)}
        {user?.role === 'admin' && renderNavGroup("Administration", adminNavItems)}
      </nav>

      <div className="p-4 border-t border-white/10">
        <button onClick={logout} className="flex items-center space-x-3 px-4 py-3 w-full rounded-xl text-red-400 hover:bg-red-500/10 transition-colors">
          <FiLogOut className="w-5 h-5" />
          <span className="font-medium">Logout</span>
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-gray-100 flex relative overflow-hidden font-sans">
      {/* Ambient background glows */}
      <div className="fixed top-[-20%] left-[-10%] w-[50%] h-[50%] bg-blue-600/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="fixed bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-purple-600/20 rounded-full blur-[120px] pointer-events-none" />

      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-64 flex-shrink-0 border-r border-white/10 bg-white/5 backdrop-blur-xl z-10 flex-col h-screen sticky top-0">
        <SidebarContent />
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 z-10 h-screen overflow-hidden">
        {/* Header */}
        <header className="h-16 md:h-20 border-b border-white/10 bg-white/5 backdrop-blur-md flex items-center justify-between px-4 md:px-8 sticky top-0 z-20 flex-shrink-0 gap-2 md:gap-4">
          <div className="flex items-center flex-1 gap-2 md:gap-4">
            {/* Mobile Hamburger Menu */}
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden text-gray-300 hover:bg-white/10 shrink-0">
                  <Menu className="h-6 w-6" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0 bg-[#0a0a0f] border-r border-white/10 text-gray-100 flex flex-col [&>button]:text-white">
                <SidebarContent />
              </SheetContent>
            </Sheet>

            <Suspense fallback={<div className="h-10 w-full max-w-xl bg-white/5 animate-pulse rounded-full" />}>
              <HeaderSearch />
            </Suspense>
          </div>

          <div className="flex items-center space-x-2 md:space-x-4">
            {user?.role === 'admin' && (
              <>
                <Button 
                  onClick={() => setShowUpload(true)} 
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white rounded-full shadow-[0_0_20px_rgba(59,130,246,0.4)] border-0 hidden sm:flex shrink-0"
                >
                  <FiUploadCloud className="w-5 h-5 mr-2" />
                  <span>Upload File</span>
                </Button>
                <Button 
                  size="icon"
                  onClick={() => setShowUpload(true)} 
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white rounded-full shadow-[0_0_20px_rgba(59,130,246,0.4)] border-0 sm:hidden shrink-0"
                >
                  <FiUploadCloud className="w-5 h-5" />
                </Button>
              </>
            )}
            
            <div className="w-8 h-8 md:w-10 md:h-10 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center border border-white/20 shadow-lg flex-shrink-0">
              <span className="font-bold text-white text-xs md:text-base">
                {user?.username ? user.username.substring(0, 2).toUpperCase() : 'US'}
              </span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 relative">
          {children}
        </div>
      </main>
      
      {showUpload && <UploadModal onClose={() => setShowUpload(false)} />}
    </div>
  );
}
