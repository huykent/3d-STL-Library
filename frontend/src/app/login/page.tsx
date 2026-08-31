'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/AuthProvider';
import { api } from '@/lib/api';

import Logo from '@/components/Logo';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { login } = useAuth();

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedUser = localStorage.getItem('saved_username');
      if (savedUser) {
        setUsername(savedUser);
      }
      const savedRemember = localStorage.getItem('remember_me');
      if (savedRemember !== null) {
        setRememberMe(savedRemember !== 'false');
      }
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // OAuth2PasswordRequestForm requires form-urlencoded data
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      formData.append('remember_me', rememberMe ? 'true' : 'false');
      
      const response = await api.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });

      if (rememberMe) {
        localStorage.setItem('saved_username', username);
        localStorage.setItem('remember_me', 'true');
      } else {
        localStorage.removeItem('saved_username');
        localStorage.setItem('remember_me', 'false');
      }

      login(response.data.access_token, rememberMe);
      router.push('/dashboard');
    } catch (err: unknown) {
      const errorResponse = err as { response?: { data?: { detail?: string } } };
      setError(errorResponse.response?.data?.detail || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900">
      <div className="max-w-md w-full p-8 bg-gray-800 rounded-lg shadow-xl border border-gray-700">
        <div className="flex justify-center mb-8">
          <Logo size="lg" />
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/50 text-red-500 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="admin"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
            />
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2.5 cursor-pointer text-sm text-gray-300 select-none hover:text-white transition-colors">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="w-4 h-4 rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800 cursor-pointer"
              />
              <span>Ghi nhớ đăng nhập</span>
            </label>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2.5 px-4 rounded-md transition-colors disabled:opacity-50 shadow-lg shadow-blue-600/20"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
