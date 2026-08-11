'use client';

import { useState, useEffect } from 'react';
import { getSettings, updateSettings, restartTelegram, verifyOtp, sendCode } from '@/lib/api';
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);
  const [message, setMessage] = useState('');

  // OTP Verification Modal
  const [showOtp, setShowOtp] = useState(false);
  const [otpPhone, setOtpPhone] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpHash, setOtpHash] = useState('');
  const [otpPassword, setOtpPassword] = useState('');
  const [needsPassword, setNeedsPassword] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const data = await getSettings();
      setSettings(data);
      if (data.TELEGRAM_PHONE) {
        setOtpPhone(data.TELEGRAM_PHONE);
      }
    } catch (error) {
      console.error("Failed to load settings", error);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key: string, value: string) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    try {
      await updateSettings(settings);
      setMessage('Settings saved successfully!');
    } catch (error) {
      setMessage('Failed to save settings.');
    } finally {
      setSaving(false);
    }
  };

  const handleLoginTelegram = async () => {
    if (!settings.TELEGRAM_PHONE) {
       setMessage('Please save your phone number first.');
       return;
    }
    setIsSending(true);
    setMessage('Sending code...');
    try {
      const res = await sendCode({ phone: settings.TELEGRAM_PHONE });
      setOtpHash(res.phone_code_hash);
      setOtpPhone(settings.TELEGRAM_PHONE);
      setShowOtp(true);
      setNeedsPassword(false);
      setOtpPassword('');
      setMessage('Code sent. Please enter it.');
    } catch (error: any) {
      setMessage('Failed to send code: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsSending(false);
    }
  };

  const handleVerifyOtp = async () => {
    setOtpLoading(true);
    try {
      const res = await verifyOtp({ 
        phone: otpPhone, 
        code: otpCode, 
        phone_code_hash: otpHash,
        password: otpPassword || undefined
      });
      if (res.status === 'password_needed') {
        setNeedsPassword(true);
        setMessage('2FA Password is required.');
      } else {
        setShowOtp(false);
        setMessage('Telegram login successful!');
      }
    } catch (error: any) {
      setMessage('OTP verification failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setOtpLoading(false);
    }
  };

  const handleRestart = async () => {
    try {
      await restartTelegram();
      setMessage('Telegram client restarted successfully!');
    } catch (error: any) {
      setMessage('Failed to restart Telegram client: ' + (error.response?.data?.detail || error.message));
    }
  };

  if (loading) return <div className="p-8 text-white">Loading settings...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">System Settings</h1>
        <p className="text-gray-400">Configure Telegram Crawler and AI tagging integrations.</p>
      </div>

      {message && (
        <div className="p-4 bg-blue-900/50 text-blue-200 border border-blue-800 rounded-lg">
          {message}
        </div>
      )}

      {/* Telegram Settings */}
      <Card className="bg-[#1c2128] border-white/10">
        <CardHeader className="flex flex-row items-center justify-between pb-4">
          <div>
            <CardTitle className="text-xl text-white">Telegram Crawler</CardTitle>
            <CardDescription>Configure your Telegram account to download models.</CardDescription>
          </div>
          <div className="space-x-3">
            <Button
              onClick={handleLoginTelegram}
              disabled={isSending}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              {isSending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Login Telegram
            </Button>
            <Button
              onClick={handleRestart}
              variant="secondary"
            >
              Restart Crawler
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">API ID</label>
              <Input
                type="text"
                value={settings.TELEGRAM_API_ID || ''}
                onChange={(e) => handleChange('TELEGRAM_API_ID', e.target.value)}
                className="bg-[#0d1117] border-white/10 text-white"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">API Hash</label>
              <Input
                type="password"
                value={settings.TELEGRAM_API_HASH || ''}
                onChange={(e) => handleChange('TELEGRAM_API_HASH', e.target.value)}
                className="bg-[#0d1117] border-white/10 text-white"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Phone Number</label>
              <Input
                type="text"
                value={settings.TELEGRAM_PHONE || ''}
                onChange={(e) => handleChange('TELEGRAM_PHONE', e.target.value)}
                placeholder="+1234567890"
                className="bg-[#0d1117] border-white/10 text-white"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Chat IDs to Monitor</label>
              <Input
                type="text"
                value={settings.TELEGRAM_CHAT_IDS || ''}
                onChange={(e) => handleChange('TELEGRAM_CHAT_IDS', e.target.value)}
                placeholder="-100123456789, -100987654321"
                className="bg-[#0d1117] border-white/10 text-white"
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium text-gray-300">Target Chat ID (Hidden Group for Uploads)</label>
              <Input
                type="text"
                value={settings.TELEGRAM_TARGET_CHAT_ID || ''}
                onChange={(e) => handleChange('TELEGRAM_TARGET_CHAT_ID', e.target.value)}
                placeholder="-1001122334455"
                className="bg-[#0d1117] border-white/10 text-white"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={showOtp} onOpenChange={setShowOtp}>
        <DialogContent className="bg-[#1c2128] border-white/10 text-white sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Enter Telegram Code</DialogTitle>
            <DialogDescription className="text-gray-400">
              We sent a code to your Telegram app at {otpPhone}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Input
              type="text"
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value)}
              placeholder="12345"
              disabled={needsPassword}
              className="bg-[#0d1117] border-white/10 text-white"
            />
            {needsPassword && (
              <>
                <p className="text-sm text-yellow-400">
                  Your account requires a 2FA password.
                </p>
                <Input
                  type="password"
                  value={otpPassword}
                  onChange={(e) => setOtpPassword(e.target.value)}
                  placeholder="Enter your 2FA password"
                  className="bg-[#0d1117] border-white/10 text-white"
                />
              </>
            )}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowOtp(false)}>Cancel</Button>
            <Button 
              onClick={handleVerifyOtp}
              disabled={otpLoading || !otpCode}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {otpLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Verify
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* AI Settings */}
      <Card className="bg-[#1c2128] border-white/10">
        <CardHeader>
          <CardTitle className="text-xl text-white">AI Tagging (Ollama)</CardTitle>
          <CardDescription>Configure your local LLM endpoint for auto-tagging.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Ollama Base URL</label>
              <Input
                type="text"
                value={settings.OLLAMA_BASE_URL || ''}
                onChange={(e) => handleChange('OLLAMA_BASE_URL', e.target.value)}
                className="bg-[#0d1117] border-white/10 text-white"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Model Name</label>
              <Input
                type="text"
                value={settings.OLLAMA_MODEL || ''}
                onChange={(e) => handleChange('OLLAMA_MODEL', e.target.value)}
                className="bg-[#0d1117] border-white/10 text-white"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={saving}
          className="bg-blue-600 hover:bg-blue-700 text-white px-8"
        >
          {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          {saving ? 'Saving...' : 'Save Settings'}
        </Button>
      </div>
    </div>
  );
}
