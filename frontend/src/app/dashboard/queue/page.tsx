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
  FiUploadCloud,
  FiMessageSquare,
  FiZap,
  FiCode,
  FiDatabase
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

interface LLMInfo {
  ollama_model?: string;
  model_filename: string;
  predicted_name: string;
  category: string;
  print_type: string;
  keywords: string[];
  system_prompt: string;
  user_prompt: string;
  raw_response: string;
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
  llm_info?: LLMInfo;
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
    total_files_backed_up?: number;
    total_gb_backed_up?: number;
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
  const [confirmAction, setConfirmAction] = useState<null | "recrawl" | "crawl-target">(null);

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

  const handleFullRecrawl = async () => {
    if (confirmAction !== "recrawl") {
      setConfirmAction("recrawl");
      return;
    }
    setConfirmAction(null);
    setReprocessing(true);
    try {
      const res = await api.post<{ status: string; message: string; groups_count: number }>("/admin/queue/full-recrawl");
      setToastMsg(res.data.message);
      fetchStatus();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to trigger full recrawl");
    } finally {
      setReprocessing(false);
      setTimeout(() => setToastMsg(""), 6000);
    }
  };

  const handleCrawlTargetGroup = async () => {
    if (confirmAction !== "crawl-target") {
      setConfirmAction("crawl-target");
      return;
    }
    setConfirmAction(null);
    setReprocessing(true);
    try {
      const res = await api.post<{ status: string; message: string }>("/admin/queue/crawl-target-group?limit=1000");
      setToastMsg(res.data.message);
      fetchStatus();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to crawl target group");
    } finally {
      setReprocessing(false);
      setTimeout(() => setToastMsg(""), 6000);
    }
  };

  useEffect(() => {
    fetchStatus();

    let intervalId: NodeJS.Timeout | null = null;

    const startPolling = () => {
      if (!intervalId) {
        intervalId = setInterval(() => {
          if (!document.hidden) {
            fetchStatus();
          }
        }, 4000);
      }
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        fetchStatus();
        startPolling();
      }
    };

    startPolling();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
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
            Giám sát thời gian thực tiến trình LLM AI Tagging, Cào dữ liệu Telegram, Xử lý 3D và Đẩy lên Nhóm Đích.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            onClick={handleFullRecrawl}
            disabled={reprocessing}
            className="bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 text-white font-medium flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg shadow-rose-500/20 text-xs md:text-sm"
          >
            <FiRefreshCw className={`w-4 h-4 ${reprocessing ? "animate-spin" : ""}`} />
            {reprocessing ? "Đang xử lý..." : "Xoá Hàng Chờ & Cào Lại"}
          </Button>
          <Button
            onClick={handleReprocessFailed}
            disabled={reprocessing}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg shadow-blue-500/20 text-xs md:text-sm"
          >
            <FiRefreshCw className={`w-4 h-4 ${reprocessing ? "animate-spin" : ""}`} />
            Thử lại file lỗi
          </Button>
          <Button
            onClick={handleCrawlTargetGroup}
            disabled={reprocessing}
            className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-medium flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg shadow-emerald-500/20 text-xs md:text-sm"
          >
            <FiDatabase className={`w-4 h-4 ${reprocessing ? "animate-spin" : ""}`} />
            Rà Nhóm Đích (Lấy Kho)
          </Button>
          <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 px-3 py-2 flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Live Sync 4s
          </Badge>
        </div>
      </div>

      {toastMsg && (
        <div className="bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 p-4 rounded-xl text-sm font-medium">
          {toastMsg}
        </div>
      )}

      {/* Inline confirmation bar */}
      {confirmAction && (
        <div className="bg-amber-500/10 border border-amber-500/40 text-amber-200 p-4 rounded-xl text-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <span>
            {confirmAction === "recrawl"
              ? "⚠️ Xác nhận: Xoá sạch hàng chờ và cào lại lịch sử toàn bộ nhóm nguồn?"
              : "⚠️ Xác nhận: Quét nhóm đích và import file mới vào DB?"}
          </span>
          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => { confirmAction === "recrawl" ? handleFullRecrawl() : handleCrawlTargetGroup(); }}
              className="bg-amber-500 hover:bg-amber-400 text-black font-bold px-4 py-1.5 rounded-lg text-xs transition-colors"
            >
              ✓ Xác nhận
            </button>
            <button
              onClick={() => setConfirmAction(null)}
              className="bg-white/10 hover:bg-white/20 text-white px-4 py-1.5 rounded-lg text-xs transition-colors"
            >
              Hủy
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* ── 🌟 Ô TO NỔI BẬT Ở TRÊN: THÔNG TIN PROMPT ĐẾN & VỀ TỪ LLM (OLLAMA) ── */}
      <Card className="bg-gradient-to-br from-purple-950/40 via-black/50 to-blue-950/40 border border-purple-500/30 backdrop-blur-xl shadow-2xl overflow-hidden">
        <CardHeader className="border-b border-purple-500/20 bg-purple-950/30 pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-xl font-bold text-white flex items-center gap-3">
              <FiZap className="w-6 h-6 text-purple-400 animate-pulse" />
              Giao Tiếp LLM AI (Ollama Prompt Input & Output)
            </CardTitle>
            <div className="flex items-center gap-2">
              <Badge className="bg-purple-500/20 text-purple-300 border-purple-500/40 font-mono text-xs">
                Ollama {data?.llm_info?.ollama_model || "AI"}
              </Badge>
              {data?.llm_info?.updated_at && (
                <span className="text-[10px] text-gray-400 font-mono">
                  Lần cuối: {new Date(data.llm_info.updated_at).toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          {data?.llm_info ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 🟢 BÊN TRÁI: PROMPT GỬI ĐẾN LLM */}
              <div className="space-y-3 bg-black/50 p-4 rounded-xl border border-blue-500/20">
                <div className="flex items-center justify-between border-b border-blue-500/20 pb-2">
                  <h3 className="text-sm font-bold text-blue-300 flex items-center gap-2">
                    <FiCode className="w-4 h-4 text-blue-400" />
                    1. Prompt Gửi Đến LLM (User Input)
                  </h3>
                  <Badge variant="outline" className="bg-blue-500/10 text-blue-300 border-blue-500/30 text-[10px] truncate max-w-[180px]">
                    {data.llm_info.model_filename}
                  </Badge>
                </div>
                <div className="space-y-2">
                  <p className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider">System Instruction:</p>
                  <pre className="bg-black/70 p-3 rounded-lg text-[11px] text-gray-300 font-mono border border-white/5 whitespace-pre-wrap max-h-28 overflow-y-auto">
                    {data.llm_info.system_prompt || "Bạn là một chuyên gia in 3D. Hãy phân tích các thông số và NỘI DUNG TIN NHẮN..."}
                  </pre>
                </div>
                <div className="space-y-2">
                  <p className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider">User Prompt Payload:</p>
                  <pre className="bg-black/70 p-3 rounded-lg text-[11px] text-cyan-300 font-mono border border-white/5 whitespace-pre-wrap max-h-36 overflow-y-auto">
                    {data.llm_info.user_prompt}
                  </pre>
                </div>
              </div>

              {/* 🟣 BÊN PHẢI: PROMPT PHẢN HỒI VỀ TỪ LLM */}
              <div className="space-y-3 bg-black/50 p-4 rounded-xl border border-purple-500/20">
                <div className="flex items-center justify-between border-b border-purple-500/20 pb-2">
                  <h3 className="text-sm font-bold text-purple-300 flex items-center gap-2">
                    <FiMessageSquare className="w-4 h-4 text-purple-400" />
                    2. Prompt Phản Hồi Về (LLM JSON Response)
                  </h3>
                  <div className="flex items-center gap-1.5">
                    <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30 text-[10px]">
                      {data.llm_info.print_type}
                    </Badge>
                    <Badge className="bg-purple-500/20 text-purple-300 border-purple-500/30 text-[10px]">
                      {data.llm_info.category}
                    </Badge>
                  </div>
                </div>

                <div className="bg-purple-950/20 p-3 rounded-lg border border-purple-500/20 space-y-1">
                  <p className="text-xs font-bold text-white">Tên dự đoán: <span className="text-purple-300">{data.llm_info.predicted_name}</span></p>
                  <div className="flex flex-wrap gap-1 pt-1">
                    {data.llm_info.keywords.map((kw, i) => (
                      <span key={i} className="text-[10px] bg-purple-500/10 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded-full">
                        #{kw}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-[11px] text-gray-400 font-semibold uppercase tracking-wider">Raw JSON Output:</p>
                  <pre className="bg-black/70 p-3 rounded-lg text-[11px] text-emerald-400 font-mono border border-white/5 whitespace-pre-wrap max-h-40 overflow-y-auto">
                    {data.llm_info.raw_response}
                  </pre>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-black/30 p-8 rounded-xl text-center space-y-2 border border-white/5">
              <FiZap className="w-8 h-8 text-purple-400/80 mx-auto" />
              <p className="text-sm font-medium text-white">Chưa Có Dữ Liệu LLM Prompt Trong Phiên Này</p>
              <p className="text-xs text-gray-400">Khi worker xử lý bài đăng mới, prompt gửi tới Ollama & kết quả trả về sẽ hiển thị realtime ở đây.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── 3 KHUNG Ở GIỮA: CÀO, PROCESSING & THÔNG TIN ĐẨY TELEGRAM ĐÍCH ────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ── KHUNG 1: THÔNG TIN CÀO (TELEGRAM CRAWLER) ─────────────────────── */}
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl flex flex-col justify-between shadow-xl">
          <CardHeader className="border-b border-white/10 bg-white/5 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-bold text-white flex items-center gap-2">
                <FiRadio className="w-4 h-4 text-cyan-400 animate-pulse" />
                1. Thông Tin Cào (Crawler)
              </CardTitle>
              <Badge className="bg-cyan-500/20 text-cyan-300 border-cyan-500/40 text-[10px]">
                {data?.crawl_info?.total_groups ?? 0} Nhóm Nguồn
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-4 space-y-3 flex-1 flex flex-col justify-between">
            <div className="bg-cyan-950/40 border border-cyan-500/30 p-3 rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
                <div>
                  <p className="text-xs font-bold text-cyan-200">Telegram Listener Active</p>
                  <p className="text-[10px] text-cyan-400/80">Lắng nghe tin nhắn mới & cào lịch sử</p>
                </div>
              </div>
            </div>

            <div className="space-y-1.5">
              <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Danh Sách Nhóm Nguồn</p>
              {(!data?.crawl_info?.source_groups || data.crawl_info.source_groups.length === 0) ? (
                <div className="bg-black/20 p-4 rounded-xl text-center text-xs text-gray-500 border border-white/5">
                  Chưa cài đặt nhóm nguồn cào Telegram.
                </div>
              ) : (
                <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
                  {data.crawl_info.source_groups.map((group) => (
                    <div
                      key={group.id}
                      className="bg-black/30 border border-white/10 p-2.5 rounded-xl flex items-center justify-between hover:border-cyan-500/40 transition-colors"
                    >
                      <div className="space-y-0.5">
                        <p className="text-xs font-bold text-white max-w-[170px] truncate">{group.name}</p>
                        <p className="text-[10px] text-gray-400 font-mono">ID: {group.chat_id} • Msg: #{group.last_message_id || 0}</p>
                      </div>
                      <Badge variant="outline" className="bg-blue-500/10 text-blue-300 border-blue-500/30 text-[10px]">
                        {group.model_count} Models
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* ── KHUNG 2: THÔNG TIN PROCESSING (3D & THUMBNAIL) ────────────────── */}
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl flex flex-col justify-between shadow-xl">
          <CardHeader className="border-b border-white/10 bg-white/5 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-bold text-white flex items-center gap-2">
                <FiCpu className="w-4 h-4 text-blue-400 animate-spin" />
                2. Thông Tin Processing (3D)
              </CardTitle>
              <Badge className="bg-blue-500/20 text-blue-300 border-blue-500/40 text-[10px]">
                {data?.processing_info?.count ?? 0} Active
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-4 space-y-3 flex-1 flex flex-col justify-between">
            {(!data?.processing_info?.active_processing || data.processing_info.active_processing.length === 0) ? (
              <div className="bg-black/20 p-6 rounded-xl text-center space-y-1.5 border border-white/5 my-auto">
                <FiCheckCircle className="w-6 h-6 text-emerald-400/80 mx-auto" />
                <p className="text-xs font-medium text-white">Không có model nào đang đo đạc 3D</p>
                <p className="text-[10px] text-gray-500">Worker sẵn sàng xử lý file tiếp theo.</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                {data.processing_info.active_processing.map((job) => {
                  const pct = getProgressPercentage(job.current_message);
                  const isExpanded = expandedLogs[job.id] ?? true;

                  return (
                    <div key={job.id} className="bg-black/40 border border-blue-500/30 p-3 rounded-xl space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-white truncate max-w-[170px]" title={job.original_filename}>
                          {job.original_filename}
                        </span>
                        <span className="text-xs font-black text-blue-400 font-mono">{pct}%</span>
                      </div>

                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] text-gray-400">
                          <span>{job.current_step}</span>
                        </div>
                        <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden border border-white/10">
                          <div
                            className="h-full bg-gradient-to-r from-blue-500 to-indigo-400 transition-all duration-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>

                      <div className="flex justify-between items-center pt-1">
                        <span className="text-[10px] text-gray-400">Msg ID: #{job.telegram_message_id}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleLogs(job.id)}
                          className="text-gray-300 hover:bg-white/10 text-[9px] h-5 px-1.5 flex items-center gap-1"
                        >
                          <FiTerminal className="w-3 h-3" /> Log {isExpanded ? <FiChevronUp /> : <FiChevronDown />}
                        </Button>
                      </div>

                      {isExpanded && (
                        <div className="bg-black/80 rounded-lg p-2 font-mono text-[9px] text-emerald-400/90 space-y-1 max-h-24 overflow-y-auto border border-white/10">
                          {job.logs.map((l, i) => (
                            <div key={i} className="leading-tight">
                              <span className="text-gray-500">[{new Date(l.time).toLocaleTimeString()}]</span> <span className="text-blue-400">[{l.step}]</span> {l.message}
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

        {/* ── KHUNG 3: THÔNG TIN ĐẨY LÊN TELEGRAM ĐÍCH (TARGET GROUP UPLOAD) ───── */}
        <Card className="bg-white/5 border-white/10 backdrop-blur-xl flex flex-col justify-between shadow-xl">
          <CardHeader className="border-b border-white/10 bg-white/5 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-bold text-white flex items-center gap-2">
                <FiSend className="w-4 h-4 text-emerald-400" />
                3. Đẩy Telegram Đích
              </CardTitle>
              <Badge variant="outline" className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40 text-[10px]">
                Target OK
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-4 space-y-3 flex-1 flex flex-col justify-between">
            <div className="bg-emerald-950/30 border border-emerald-500/30 p-3 rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FiUploadCloud className="w-4 h-4 text-emerald-400" />
                <div>
                  <p className="text-xs font-bold text-emerald-200">Nhóm Đích Lưu Trữ</p>
                  <p className="text-[10px] font-mono text-emerald-400/80">ID: {data?.target_upload_info?.target_chat_id ?? "Chưa cấu hình"}</p>
                </div>
              </div>
            </div>

            {/* ── BẢNG ĐẾM DUNG LƯỢNG & TỔNG FILE TRÊN NHÓM ĐÍCH ── */}
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-gradient-to-br from-emerald-500/15 to-emerald-900/20 border border-emerald-500/30 p-2.5 rounded-xl shadow-inner">
                <span className="text-[10px] text-emerald-400 font-semibold uppercase tracking-wider block">File Trên Kênh Đích</span>
                <div className="flex items-baseline gap-1 mt-0.5">
                  <span className="text-xl font-black text-white font-mono tracking-tight">
                    {data?.target_upload_info?.total_files_backed_up?.toLocaleString() ?? 0}
                  </span>
                  <span className="text-[10px] text-emerald-400 font-medium">file</span>
                </div>
              </div>
              <div className="bg-gradient-to-br from-blue-500/15 to-indigo-900/20 border border-blue-500/30 p-2.5 rounded-xl shadow-inner">
                <span className="text-[10px] text-blue-400 font-semibold uppercase tracking-wider block">Dung Lượng Đã Lưu</span>
                <div className="flex items-baseline gap-1 mt-0.5">
                  <span className="text-xl font-black text-white font-mono tracking-tight">
                    {data?.target_upload_info?.total_gb_backed_up ?? 0}
                  </span>
                  <span className="text-[10px] text-blue-400 font-medium">GB</span>
                </div>
              </div>
            </div>

            <div className="space-y-1.5">
              <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Bài Mới Đăng Gần Đây</p>
              {(!data?.target_upload_info?.recent_uploads || data.target_upload_info.recent_uploads.length === 0) ? (
                <div className="bg-black/20 p-4 rounded-xl text-center text-xs text-gray-500 border border-white/5">
                  Chưa có bài đăng gần đây.
                </div>
              ) : (
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1">
                  {data.target_upload_info.recent_uploads.map((item) => (
                    <div
                      key={item.id}
                      className="bg-black/30 border border-white/10 p-2.5 rounded-xl flex items-center justify-between"
                    >
                      <div className="space-y-0.5 max-w-[150px]">
                        <p className="text-xs font-medium text-white truncate" title={item.original_filename}>
                          {item.original_filename}
                        </p>
                        <p className="text-[9px] text-gray-500 font-mono">
                          {item.source_group_name}
                        </p>
                      </div>
                      <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[9px]">
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

      {/* ── 🔽 KHUNG 4 Ở CUỐI: THÔNG TIN HÀNG CHỜ (QUEUE STATUS & PENDING LIST) ── */}
      <Card className="bg-white/5 border-white/10 backdrop-blur-xl shadow-xl">
        <CardHeader className="border-b border-white/10 bg-white/5 pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-xl font-bold text-white flex items-center gap-3">
              <FiClock className="w-6 h-6 text-amber-400" />
              4. Thông Tin Hàng Chờ & Thống Kê Tổng Quan (Queue Status)
            </CardTitle>
            <Badge variant="outline" className="bg-amber-500/20 text-amber-300 border-amber-500/40 text-xs">
              {data?.queue_info?.queued_count ?? 0} Task Trong Hàng Chờ
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          {/* Metrics Overview */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-black/30 p-4 rounded-xl border border-white/5 text-center">
              <p className="text-xs text-gray-400 uppercase tracking-wider font-semibold">Đang Chờ Xử Lý</p>
              <p className="text-3xl font-bold text-amber-400 mt-2">{data?.summary?.queued_count ?? 0}</p>
              <p className="text-[10px] text-gray-500 mt-1">Pending in Redis Queue</p>
            </div>
            <div className="bg-black/30 p-4 rounded-xl border border-white/5 text-center">
              <p className="text-xs text-gray-400 uppercase tracking-wider font-semibold">Hoàn Thành Hôm Nay</p>
              <p className="text-3xl font-bold text-emerald-400 mt-2">{data?.summary?.completed_today_count ?? 0}</p>
              <p className="text-[10px] text-gray-500 mt-1">Processed Today</p>
            </div>
            <div className="bg-black/30 p-4 rounded-xl border border-white/5 text-center">
              <p className="text-xs text-gray-400 uppercase tracking-wider font-semibold">Tốc Độ Xử Lý Trung Bình</p>
              <p className="text-3xl font-bold text-purple-400 mt-2">~{data?.summary?.avg_processing_time_sec ?? 18}s</p>
              <p className="text-[10px] text-gray-500 mt-1">Per Model Pipeline</p>
            </div>
          </div>

          {/* Pending Queue Table */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Danh Sách Chi Tiết Hàng Chờ Redis</p>
            {(!data?.queued_jobs || data.queued_jobs.length === 0) ? (
              <div className="bg-black/20 p-8 rounded-xl text-center text-xs text-gray-500 border border-white/5">
                Hàng chờ trống. Tất cả các task đã được xử lý xong!
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-white/10 bg-black/40">
                <table className="w-full text-left text-xs text-gray-300">
                  <thead className="bg-white/5 text-[10px] text-gray-400 uppercase tracking-wider border-b border-white/10">
                    <tr>
                      <th className="p-4">Vị Trí #</th>
                      <th className="p-4">Tên File 3D</th>
                      <th className="p-4">Nhóm Nguồn</th>
                      <th className="p-4">Dung Lượng</th>
                      <th className="p-4">Trạng Thái</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {data?.queued_jobs.map((item, idx) => (
                      <tr key={item.id} className="hover:bg-white/5 transition-colors">
                        <td className="p-4 font-mono text-amber-400 font-bold">#{idx + 1}</td>
                        <td className="p-4 font-medium text-white max-w-sm truncate" title={item.original_filename}>
                          {item.original_filename}
                        </td>
                        <td className="p-4 text-gray-400">{item.source_group_name}</td>
                        <td className="p-4 font-mono">{(item.file_size_bytes / (1024 * 1024)).toFixed(1)} MB</td>
                        <td className="p-4">
                          <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/30">
                            Pending Queue
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

    </div>
  );
}
