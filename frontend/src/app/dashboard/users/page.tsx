"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { getAdminUsers, updateAdminUser } from "@/lib/api";
import { useRouter } from "next/navigation";
import { formatDistanceToNow } from "date-fns";

export default function UsersPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<string | null>(null);

  useEffect(() => {
    if (user?.role !== "admin") {
      router.push("/dashboard");
      return;
    }
    
    fetchUsers();
  }, [user, router]);

  const fetchUsers = async () => {
    try {
      const data = await getAdminUsers();
      setUsers(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    setUpdating(userId);
    try {
      await updateAdminUser(userId, { role: newRole });
      setUsers(users.map(u => u.id === userId ? { ...u, role: newRole } : u));
    } catch (error) {
      console.error("Failed to update role", error);
    } finally {
      setUpdating(null);
    }
  };

  const handleStatusChange = async (userId: string, isActive: boolean) => {
    setUpdating(userId);
    try {
      await updateAdminUser(userId, { is_active: isActive });
      setUsers(users.map(u => u.id === userId ? { ...u, is_active: isActive } : u));
    } catch (error) {
      console.error("Failed to update status", error);
    } finally {
      setUpdating(null);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
          User Management
        </h1>
        <p className="text-gray-400 mt-2">Manage system users, roles, and access.</p>
      </div>

      <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-400">
            <thead className="bg-black/20 text-gray-300 uppercase font-medium border-b border-white/10">
              <tr>
                <th className="px-6 py-4">User</th>
                <th className="px-6 py-4">Role</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center flex-shrink-0 text-white font-bold">
                        {u.username.substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div className="text-white font-medium">{u.username}</div>
                        <div className="text-xs text-gray-500">{u.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      disabled={updating === u.id || u.username === "admin"}
                      className="bg-black/30 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500 disabled:opacity-50"
                    >
                      <option value="admin">Admin</option>
                      <option value="viewer">Viewer</option>
                    </select>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => handleStatusChange(u.id, !u.is_active)}
                      disabled={updating === u.id || u.username === "admin"}
                      className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors disabled:opacity-50 ${
                        u.is_active 
                          ? "bg-green-500/10 text-green-400 border-green-500/20 hover:bg-green-500/20" 
                          : "bg-red-500/10 text-red-400 border-red-500/20 hover:bg-red-500/20"
                      }`}
                    >
                      {u.is_active ? "Active" : "Disabled"}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-xs text-gray-500">
                    ID: {u.id.split("-")[0]}...
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
