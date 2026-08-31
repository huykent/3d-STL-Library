'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { getCurrentUser } from '@/lib/api';

export interface User {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'viewer';
  is_active: boolean;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  token: string | null;
  user: User | null;
  login: (token: string, remember?: boolean) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  isLoading: true,
  token: null,
  user: null,
  login: () => {},
  logout: () => {},
  refreshUser: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMounted, setIsMounted] = useState(false);

  const fetchUser = async (authToken?: string) => {
    try {
      // API interceptor uses storage, but if we just logged in we might need a tick
      const userData = await getCurrentUser();
      setUser(userData);
    } catch (error) {
      console.error('Failed to fetch user', error);
      setUser(null);
      setToken(null);
      localStorage.removeItem('access_token');
      sessionStorage.removeItem('access_token');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setIsMounted(true);
    const storedToken = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    if (storedToken) {
      setToken(storedToken);
      fetchUser();
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = (newToken: string, remember: boolean = true) => {
    if (remember) {
      localStorage.setItem('access_token', newToken);
      sessionStorage.removeItem('access_token');
    } else {
      sessionStorage.setItem('access_token', newToken);
      localStorage.removeItem('access_token');
    }
    setToken(newToken);
    setIsLoading(true);
    fetchUser(newToken);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    sessionStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
    window.location.href = '/login';
  };

  if (!isMounted) {
    return null;
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!token, isLoading, token, user, login, logout, refreshUser: fetchUser }}>
      {children}
    </AuthContext.Provider>
  );
}
