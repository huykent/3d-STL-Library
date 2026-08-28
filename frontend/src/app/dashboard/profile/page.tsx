"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { updateCurrentUser } from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const [email, setEmail] = useState(user?.email || "");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      const updateData: any = {};
      if (email !== user?.email) updateData.email = email;
      if (password) updateData.password = password;

      if (Object.keys(updateData).length > 0) {
        await updateCurrentUser(updateData);
        await refreshUser();
        setMessage("Profile updated successfully!");
        setPassword("");
      } else {
        setMessage("No changes to update.");
      }
    } catch (error) {
      console.error(error);
      setMessage("Failed to update profile.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
          My Profile
        </h1>
        <p className="text-gray-400 mt-2">Manage your account settings and credentials.</p>
      </div>

      <div className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
        <form onSubmit={handleUpdate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Username</label>
            <input
              type="text"
              value={user?.username || ""}
              disabled
              className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-2.5 text-gray-500 cursor-not-allowed"
            />
            <p className="text-xs text-gray-500 mt-1">Username cannot be changed.</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Role</label>
            <div className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-2.5 text-blue-400 uppercase text-sm font-semibold tracking-wider">
              {user?.role}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">New Password (Optional)</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Leave blank to keep current password"
              className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all"
            />
          </div>

          {message && (
            <div className={`p-4 rounded-xl text-sm ${message.includes("success") ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>
              {message}
            </div>
          )}

          <div className="pt-4 border-t border-white/10">
            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white rounded-xl py-6"
            >
              {loading ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
