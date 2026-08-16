"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FiActivity, FiClock, FiCheckCircle, FiServer, FiChevronDown, FiChevronUp, FiTerminal, FiRefreshCw } from "react-icons/fi";



interface ProcessingLog {
  step: string;
  message: string;
  time: string;
}

interface ActiveJob {
  id: string;
  original_filename: string;
  source_group_name: string;
  telegram_message_id: number;
  file_size_bytes: number;
  processing_status: string;
  current_step: string;
  current_message: string;
  updated_at?: string;
  logs: ProcessingLog[];
}

interface QueuedJob {
  id: string;
  original_filename: string;
  source_group_name: string;
  telegram_message_id: number;
  file_size_bytes: number;
  created_at?: string;
}

interface QueueSummary {
  active_count: number;
  queued_count: number;
  completed_today_count: number;
  avg_processing_time_sec: number;
}

interface QueueStatusResponse {
  summary: QueueSummary;
  active_jobs: ActiveJob[];
  queued_jobs: QueuedJob[];
}

export default function ActiveQueuePage() {
  const [data, setData] = useState<QueueStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedLogs, setExpandedLogs] = useState<Record<string, boolean>>({});
  const [reprocessing, setReprocessing] = useState(false);
  const [toastMsg, setToastMsg] = useState("");

  const fetchStatus = async () => {
    try {
      const response = await api.get<QueueStatusResponse>("/admin/queue/status");
      setData(response.data);
      setError("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to fetch queue status");
    } finally {
      setLoading(false);
    }
  };

  const handleReprocessFailed = async () => {
    setReprocessing(true);
    try {
      const res = await api.post<{ status: string; message: string; requeued_count: number }>("/admin/queue/reprocess-failed");
      setToastMsg(res.data.message);
      fetchStatus();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to reprocess failed models");
    } finally {
      setReprocessing(false);
      setTimeout(() => setToastMsg(""), 5000);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const toggleLogs = (id: string) => {
    setExpandedLogs((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getProgressPercentage = (stepMsg: string = "") => {
    const match = stepMsg.match(/\[(\d+)%\]/);
    if (match) return parseInt(match[1], 10);
    if (stepMsg.includes("Tải file")) return 20;
    if (stepMsg.includes("Xả nén")) return 40;
    if (stepMsg.includes("Đo đạc 3D")) return 60;
    if (stepMsg.includes("Thumbnail")) return 75;
    if (stepMsg.includes("AI Tag")) return 90;
    if (stepMsg.includes("Backup") || stepMsg.includes("Upload")) return 98;
    if (stepMsg.includes("Hoàn tất")) return 100;
    return 15;
  };

  return (
    <div className="p-6 md:p-10 space-y-8 max-w-7xl mx-auto">
      {/* Header Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3 tracking-tight">
            <FiActivity className="text-blue-400 animate-pulse w-8 h-8" />
            Active Worker Queue & Live Progress
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Real-time monitoring of Telegram 3D model crawling, geometry extraction, AI tagging, and backup uploads.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={handleReprocessFailed}
            disabled={reprocessing}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg shadow-blue-500/20"
          >
            <FiRefreshCw className={`w-4 h-4 ${reprocessing ? "animate-spin" : ""}`} />
            {reprocessing ? "Đang đẩy vào hàng chờ..." : "Thử lại các file lỗi"}
          </Button>
          <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 px-3 py-2 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Auto-Sync 2s
          </Badge>
        </div>
      </div>

      {toastMsg && (
        <div className="bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 p-4 rounded-xl text-sm font-medium">
          {toastMsg}
        </div>
      )}


      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Processing Now</CardTitle>
            <FiActivity className="w-5 h-5 text-blue-400 animate-spin" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-white">
              {data?.summary.active_count ?? 0}
            </div>
            <p className="text-xs text-gray-500 mt-1">Active worker models</p>
          </CardContent>
        </Card>

        <Card className="bg-white/5 border-white/10 backdrop-blur-xl">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Queued Tasks</CardTitle>
            <FiClock className="w-5 h-5 text-amber-400" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-white">
              {data?.summary.queued_count ?? 0}
            </div>
            <p className="text-xs text-gray-500 mt-1">Pending in Redis queue</p>
          </CardContent>
        </Card>

        <Card className="bg-white/5 border-white/10 backdrop-blur-xl">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Completed Today</CardTitle>
            <FiCheckCircle className="w-5 h-5 text-emerald-400" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-white">
              {data?.summary.completed_today_count ?? 0}
            </div>
            <p className="text-xs text-gray-500 mt-1">Processed models today</p>
          </CardContent>
        </Card>

        <Card className="bg-white/5 border-white/10 backdrop-blur-xl">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Avg Speed</CardTitle>
            <FiServer className="w-5 h-5 text-purple-400" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-white">
              ~{data?.summary.avg_processing_time_sec ?? 18}s
            </div>
            <p className="text-xs text-gray-500 mt-1">Per 3D model processing</p>
          </CardContent>
        </Card>
      </div>

      {/* Active Processing Section */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-blue-500 animate-ping" />
          Active Processing Models ({data?.active_jobs.length ?? 0})
        </h2>

        {data?.active_jobs.length === 0 ? (
          <Card className="bg-white/5 border-white/10 p-12 text-center">
            <div className="flex flex-col items-center justify-center text-gray-400 space-y-3">
              <FiCheckCircle className="w-12 h-12 text-emerald-400/80" />
              <h3 className="text-lg font-medium text-white">No Models Currently Processing</h3>
              <p className="text-sm text-gray-500 max-w-md">
                Worker is idle or background Telegram crawler is scanning groups for new 3D print files.
              </p>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {data?.active_jobs.map((job) => {
              const pct = getProgressPercentage(job.current_message);
              const isExpanded = expandedLogs[job.id] ?? true;

              return (
                <Card key={job.id} className="bg-white/5 border-blue-500/30 overflow-hidden shadow-lg shadow-blue-500/5">
                  <CardHeader className="pb-3 border-b border-white/10 bg-white/5">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-3">
                          <h3 className="text-lg font-bold text-white truncate max-w-xl" title={job.original_filename}>
                            {job.original_filename}
                          </h3>
                          <Badge variant="outline" className="bg-blue-500/20 text-blue-300 border-blue-500/40">
                            {job.source_group_name}
                          </Badge>
                        </div>
                        <p className="text-xs text-gray-400 mt-1">
                          Msg ID: #{job.telegram_message_id} • Size: {(job.file_size_bytes / (1024 * 1024)).toFixed(1)} MB
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className="text-2xl font-black text-blue-400 font-mono">
                          {pct}%
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleLogs(job.id)}
                          className="text-gray-300 hover:bg-white/10 flex items-center gap-1 text-xs"
                        >
                          <FiTerminal className="w-4 h-4" />
                          {isExpanded ? <FiChevronUp className="w-4 h-4" /> : <FiChevronDown className="w-4 h-4" />}
                        </Button>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="p-6 space-y-4">
                    {/* Live Progress Bar */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs text-gray-400 font-medium">
                        <span>Current Phase: <strong className="text-blue-300">{job.current_step}</strong></span>
                        <span>{job.current_message}</span>
                      </div>
                      <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden p-0.5 border border-white/10">
                        <div
                          className="h-full bg-gradient-to-r from-blue-500 via-indigo-400 to-cyan-400 rounded-full transition-all duration-500 ease-out shadow-[0_0_12px_rgba(59,130,246,0.5)]"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>

                    {/* Console Logs Dropdown */}
                    {isExpanded && (
                      <div className="bg-black/60 rounded-xl p-4 font-mono text-xs text-gray-300 border border-white/10 space-y-2 max-h-48 overflow-y-auto">
                        <div className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold mb-2">
                          Live Processing Console Output
                        </div>
                        {job.logs.map((log, idx) => (
                          <div key={idx} className="flex gap-3 text-emerald-400/90 leading-relaxed">
                            <span className="text-gray-500 shrink-0">
                              {new Date(log.time).toLocaleTimeString()}
                            </span>
                            <span className="font-semibold text-blue-400 shrink-0">
                              [{log.step}]
                            </span>
                            <span className="text-gray-200">
                              {log.message}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Queued Models List */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
          <FiClock className="text-amber-400" />
          Pending Queue List ({data?.queued_jobs.length ?? 0})
        </h2>

        {data?.queued_jobs.length === 0 ? (
          <Card className="bg-white/5 border-white/10 p-6 text-center text-gray-500 text-sm">
            No pending models in queue.
          </Card>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-white/10 bg-white/5">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="bg-white/5 text-xs text-gray-400 uppercase tracking-wider border-b border-white/10">
                <tr>
                  <th className="p-4"># Pos</th>
                  <th className="p-4">Filename</th>
                  <th className="p-4">Group</th>
                  <th className="p-4">Size</th>
                  <th className="p-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data?.queued_jobs.map((qJob, index) => (
                  <tr key={qJob.id} className="hover:bg-white/5 transition-colors">
                    <td className="p-4 font-mono font-bold text-amber-400">#{index + 1}</td>
                    <td className="p-4 font-medium text-white max-w-xs truncate">{qJob.original_filename}</td>
                    <td className="p-4 text-gray-400">{qJob.source_group_name}</td>
                    <td className="p-4 font-mono">{(qJob.file_size_bytes / (1024 * 1024)).toFixed(1)} MB</td>
                    <td className="p-4">
                      <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/30">
                        Queued
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
