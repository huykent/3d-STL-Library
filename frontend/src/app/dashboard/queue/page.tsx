"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  FiActivity,
  FiClock,
  FiCheckCircle,
  FiServer,
  FiChevronDown,
  FiChevronUp,
  FiTerminal,
  FiRefreshCw,
  FiRadio,
  FiSend,
  FiCpu,
  FiLayers,
  FiDatabase,
  FiUploadCloud
} from "react-icons/fi";

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

interface SourceGroupItem {
  id: number;
  chat_id: number;
  name: string;
  model_count: number;
  is_active: boolean;
  last_message_id?: number;
}

interface RecentUploadItem {
  id: string;
  original_filename: string;
  source_group_name: string;
  telegram_file_id: string;
  face_count?: number;
  updated_at?: string;
}

interface QueueSummary {
  active_count: number;
  queued_count: number;
  completed_today_count: number;
  avg_processing_time_sec: number;
}

interface QueueStatusResponse {
  summary: QueueSummary;
  queue_info: {
    queued_jobs: QueuedJob[];
    queued_count: number;
    completed_today_count: number;
  };
  crawl_info: {
    status: string;
    source_groups: SourceGroupItem[];
    total_groups: number;
  };
  processing_info: {
    active_processing: ActiveJob[];
    count: number;
  };
  target_upload_info: {
    target_chat_id: string;
    active_uploads: ActiveJob[];
    recent_uploads: RecentUploadItem[];
  };
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
    <div className="p-4 md:p-8 space-y-8 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/5 border border-white/10 p-6 rounded-2xl backdrop-blur-xl">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-white flex items-center gap-3 tracking-tight">
            <FiLayers className="text-blue-400 w-7 h-7" />
            Hệ Thống Quản Lý Hàng Chờ & Live Processing
          </h1>
          <p className="text-xs md:text-sm text-gray-400 mt-1">
            Giám sát thời gian thực tiến trình Cào dữ liệu Telegram, Xử lý 3D/AI và Đẩy lên Nhóm Đích.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={handleReprocessFailed}
            disabled={reprocessing}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg shadow-blue-500/20 text-xs md:text-sm"
          >
            <FiRefreshCw className={`w-4 h-4 ${reprocessing ? "animate-spin" : ""}`} />
            {reprocessing ? "Đang xử lý..." : "Thử lại file lỗi & chưa upload"}
          </Button>
          <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 px-3 py-2 flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Live Sync 2s
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

      {/* ── GRID 4 KHUNG ĐỘC LẬP ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── KHUNG 1: THÔNG TIN HÀNG CHỜ (QUEUE STATUS & PENDING TASKS) ──────── */}
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl flex flex-col justify-between shadow-xl">
          <CardHeader className="border-b border-white/10 bg-white/5 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2.5">
                <FiClock className="w-5 h-5 text-amber-400" />
                1. Thông Tin Hàng Chờ (Queue)
              </CardTitle>
              <Badge variant="outline" className="bg-amber-500/20 text-amber-300 border-amber-500/40">
                {data?.queue_info?.queued_count ?? 0} Đang Đợi
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-4 flex-1 flex flex-col justify-between">
            {/* Quick Metrics */}
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="bg-black/30 p-3 rounded-xl border border-white/5">
                <p className="text-[11px] text-gray-400 uppercase tracking-wider">Trong Chờ</p>
                <p className="text-xl font-bold text-amber-400 mt-1">{data?.summary?.queued_count ?? 0}</p>
              </div>
              <div className="bg-black/30 p-3 rounded-xl border border-white/5">
                <p className="text-[11px] text-gray-400 uppercase tracking-wider">Xong Hôm Nay</p>
                <p className="text-xl font-bold text-emerald-400 mt-1">{data?.summary?.completed_today_count ?? 0}</p>
              </div>
              <div className="bg-black/30 p-3 rounded-xl border border-white/5">
                <p className="text-[11px] text-gray-400 uppercase tracking-wider">Tốc Độ TB</p>
                <p className="text-xl font-bold text-purple-400 mt-1">~{data?.summary?.avg_processing_time_sec ?? 18}s</p>
              </div>
            </div>

            {/* Pending List Table */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Danh Sách File Chờ Xử Lý</p>
              {(!data?.queued_jobs || data.queued_jobs.length === 0) ? (
                <div className="bg-black/20 p-6 rounded-xl text-center text-xs text-gray-500 border border-white/5">
                  Hàng chờ trống. Không có model nào đang đợi.
                </div>
              ) : (
                <div className="max-h-56 overflow-y-auto rounded-xl border border-white/10 bg-black/40">
                  <table className="w-full text-left text-xs text-gray-300">
                    <thead className="bg-white/5 text-[10px] text-gray-400 uppercase border-b border-white/10">
                      <tr>
                        <th className="p-3">Pos</th>
                        <th className="p-3">Tên File</th>
                        <th className="p-3">Nguồn</th>
                        <th className="p-3">Size</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {data?.queued_jobs.map((item, idx) => (
                        <tr key={item.id} className="hover:bg-white/5">
                          <td className="p-3 font-mono text-amber-400 font-bold">#{idx + 1}</td>
                          <td className="p-3 font-medium text-white max-w-[150px] truncate" title={item.original_filename}>
                            {item.original_filename}
                          </td>
                          <td className="p-3 text-gray-400 max-w-[100px] truncate">{item.source_group_name}</td>
                          <td className="p-3 font-mono">{(item.file_size_bytes / (1024 * 1024)).toFixed(1)} MB</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* ── KHUNG 2: THÔNG TIN CÀO (TELEGRAM CRAWLER STATUS) ──────────────── */}
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl flex flex-col justify-between shadow-xl">
          <CardHeader className="border-b border-white/10 bg-white/5 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2.5">
                <FiRadio className="w-5 h-5 text-cyan-400 animate-pulse" />
                2. Thông Tin Cào (Telegram Crawler)
              </CardTitle>
              <Badge className="bg-cyan-500/20 text-cyan-300 border-cyan-500/40">
                Userbot Active
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-4 flex-1 flex flex-col justify-between">
            {/* Status Header */}
            <div className="bg-cyan-950/40 border border-cyan-500/30 p-3.5 rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="w-3 h-3 rounded-full bg-cyan-400 animate-ping" />
                <div>
                  <p className="text-xs font-bold text-cyan-200">Trạng Thái Telegram Listener</p>
                  <p className="text-[11px] text-cyan-400/80">Tự động lắng nghe tin nhắn mới & cào lịch sử</p>
                </div>
              </div>
              <Badge variant="outline" className="bg-black/40 text-cyan-300 border-cyan-500/30 text-xs font-mono">
                {data?.crawl_info?.total_groups ?? 0} Nhóm Nguồn
              </Badge>
            </div>

            {/* Source Groups List */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Danh Sách Nhóm Đang Quét</p>
              {(!data?.crawl_info?.source_groups || data.crawl_info.source_groups.length === 0) ? (
                <div className="bg-black/20 p-6 rounded-xl text-center text-xs text-gray-500 border border-white/5">
                  Chưa cài đặt nhóm nguồn cào Telegram.
                </div>
              ) : (
                <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
                  {data.crawl_info.source_groups.map((group) => (
                    <div
                      key={group.id}
                      className="bg-black/30 border border-white/10 p-3 rounded-xl flex items-center justify-between hover:border-cyan-500/40 transition-colors"
                    >
                      <div className="space-y-0.5">
                        <p className="text-xs font-bold text-white max-w-[200px] truncate">{group.name}</p>
                        <p className="text-[10px] text-gray-400 font-mono">ID: {group.chat_id} • Msg: #{group.last_message_id || 0}</p>
                      </div>
                      <div className="text-right">
                        <Badge variant="outline" className="bg-blue-500/10 text-blue-300 border-blue-500/30 text-[10px]">
                          {group.model_count} Models
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* ── KHUNG 3: THÔNG TIN PROCESSING (3D GEOMETRY, AI & THUMBNAIL) ────── */}
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl flex flex-col justify-between shadow-xl">
          <CardHeader className="border-b border-white/10 bg-white/5 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2.5">
                <FiCpu className="w-5 h-5 text-blue-400 animate-spin" />
                3. Thông Tin Processing (3D & AI)
              </CardTitle>
              <Badge className="bg-blue-500/20 text-blue-300 border-blue-500/40">
                {data?.processing_info?.count ?? 0} Models Đang Xử Lý
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-4 flex-1 flex flex-col justify-between">
            {(!data?.processing_info?.active_processing || data.processing_info.active_processing.length === 0) ? (
              <div className="bg-black/20 p-8 rounded-xl text-center space-y-2 border border-white/5 my-auto">
                <FiCheckCircle className="w-8 h-8 text-emerald-400/80 mx-auto" />
                <p className="text-xs font-medium text-white">Không có model nào đang đo đạc 3D / AI</p>
                <p className="text-[11px] text-gray-500">Worker đang ở trạng thái chờ sẵn sàng.</p>
              </div>
            ) : (
              <div className="space-y-4 max-h-80 overflow-y-auto pr-1">
                {data.processing_info.active_processing.map((job) => {
                  const pct = getProgressPercentage(job.current_message);
                  const isExpanded = expandedLogs[job.id] ?? true;

                  return (
                    <div key={job.id} className="bg-black/40 border border-blue-500/30 p-4 rounded-xl space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-white truncate max-w-[220px]" title={job.original_filename}>
                          {job.original_filename}
                        </span>
                        <span className="text-xs font-black text-blue-400 font-mono">{pct}%</span>
                      </div>

                      {/* Progress Bar */}
                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] text-gray-400">
                          <span>{job.current_step}</span>
                          <span className="truncate max-w-[180px]">{job.current_message}</span>
                        </div>
                        <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden border border-white/10">
                          <div
                            className="h-full bg-gradient-to-r from-blue-500 to-indigo-400 transition-all duration-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>

                      {/* Log Console */}
                      <div className="flex justify-between items-center pt-1">
                        <span className="text-[10px] text-gray-400">Msg ID: #{job.telegram_message_id}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleLogs(job.id)}
                          className="text-gray-300 hover:bg-white/10 text-[10px] h-6 px-2 flex items-center gap-1"
                        >
                          <FiTerminal className="w-3 h-3" />
                          Log Console {isExpanded ? <FiChevronUp /> : <FiChevronDown />}
                        </Button>
                      </div>

                      {isExpanded && (
                        <div className="bg-black/80 rounded-lg p-3 font-mono text-[10px] text-emerald-400/90 space-y-1 max-h-32 overflow-y-auto border border-white/10">
                          {job.logs.map((l, i) => (
                            <div key={i} className="leading-tight">
                              <span className="text-gray-500">[{new Date(l.time).toLocaleTimeString()}]</span>{" "}
                              <span className="text-blue-400 font-bold">[{l.step}]</span> {l.message}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── KHUNG 4: THÔNG TIN ĐẨY LÊN TELEGRAM ĐÍCH (TARGET GROUP UPLOAD) ───── */}
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl flex flex-col justify-between shadow-xl">
          <CardHeader className="border-b border-white/10 bg-white/5 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-bold text-white flex items-center gap-2.5">
                <FiSend className="w-5 h-5 text-emerald-400" />
                4. Thông Tin Đẩy Telegram Đích
              </CardTitle>
              <Badge variant="outline" className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40">
                Target Chat Configured
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-4 flex-1 flex flex-col justify-between">
            {/* Target Channel Info */}
            <div className="bg-emerald-950/30 border border-emerald-500/30 p-3.5 rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <FiUploadCloud className="w-5 h-5 text-emerald-400" />
                <div>
                  <p className="text-xs font-bold text-emerald-200">Nhóm Đích Lưu Trữ</p>
                  <p className="text-[10px] font-mono text-emerald-400/80">ID: {data?.target_upload_info?.target_chat_id ?? "Chưa cấu hình"}</p>
                </div>
              </div>
              <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30 text-[10px]">
                Auto Backup 98%
              </Badge>
            </div>

            {/* Active Uploads */}
            {data?.target_upload_info?.active_uploads && data.target_upload_info.active_uploads.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  Đang Upload Sang Nhóm Đích
                </p>
                {data.target_upload_info.active_uploads.map((uJob) => (
                  <div key={uJob.id} className="bg-emerald-950/40 border border-emerald-500/40 p-3 rounded-xl space-y-2">
                    <p className="text-xs font-bold text-white truncate">{uJob.original_filename}</p>
                    <p className="text-[10px] text-emerald-300">{uJob.current_message}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Recent Uploaded Items List */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Bài Mới Đăng Nhóm Đích Gần Đây</p>
              {(!data?.target_upload_info?.recent_uploads || data.target_upload_info.recent_uploads.length === 0) ? (
                <div className="bg-black/20 p-6 rounded-xl text-center text-xs text-gray-500 border border-white/5">
                  Chưa có bài đăng gần đây.
                </div>
              ) : (
                <div className="max-h-52 overflow-y-auto space-y-2 pr-1">
                  {data.target_upload_info.recent_uploads.map((item) => (
                    <div
                      key={item.id}
                      className="bg-black/30 border border-white/10 p-2.5 rounded-xl flex items-center justify-between"
                    >
                      <div className="space-y-0.5 max-w-[200px]">
                        <p className="text-xs font-medium text-white truncate" title={item.original_filename}>
                          {item.original_filename}
                        </p>
                        <p className="text-[10px] text-gray-500 font-mono">
                          {item.source_group_name} • {item.face_count ? `${item.face_count.toLocaleString()} faces` : 'Ok'}
                        </p>
                      </div>
                      <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[10px]">
                        ✓ Backup OK
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
