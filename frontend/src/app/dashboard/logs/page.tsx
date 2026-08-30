'use client';

import { useEffect, useState, useRef } from 'react';
import { FiTerminal, FiTrash2, FiPlay, FiPause, FiDownload } from 'react-icons/fi';

interface LogMessage {
  timestamp: string;
  level: string;
  process: string;
  message: string;
  logger: string;
}

const isSqlLog = (msg: string, loggerName?: string) => {
  if (loggerName && (loggerName.startsWith('sqlalchemy') || loggerName.startsWith('asyncpg'))) {
    return true;
  }
  if (!msg) return false;
  const upper = msg.trim().toUpperCase();
  return (
    upper.startsWith('SELECT ') ||
    upper.startsWith('UPDATE ') ||
    upper.startsWith('INSERT ') ||
    upper.startsWith('DELETE ') ||
    upper.startsWith('BEGIN') ||
    upper.startsWith('COMMIT') ||
    upper.startsWith('ROLLBACK') ||
    upper.includes('[CACHED SINCE') ||
    upper.includes('FROM MODELS_3D') ||
    upper.includes('INTO MODELS_3D')
  );
};

export default function SystemLogsPage() {
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [isPaused, setIsPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [hideSql, setHideSql] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const ws = useRef<WebSocket | null>(null);
  
  // Use a ref for isPaused to access current value inside websocket closure
  const isPausedRef = useRef(isPaused);
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);

  useEffect(() => {
    // Only works in browser
    if (typeof window === 'undefined') return;
    
    // Connect to websocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // For local dev it's typically proxying /api, but let's point to the API base URL if needed
    // Assuming API is on same origin under /api/admin/logs/stream
    const wsUrl = `${protocol}//${window.location.host}/api/admin/logs/stream`;
    
    // During dev, the API might be on port 8000
    const finalWsUrl = process.env.NODE_ENV === 'development' 
      ? 'ws://localhost:8000/api/admin/logs/stream' 
      : wsUrl;

    ws.current = new WebSocket(finalWsUrl);

    ws.current.onmessage = (event) => {
      if (isPausedRef.current) return;
      
      try {
        const data: LogMessage = JSON.parse(event.data);
        setLogs((prev) => {
          const newLogs = [...prev, data];
          // Keep only last 1000 logs to prevent memory issues
          if (newLogs.length > 1000) return newLogs.slice(newLogs.length - 1000);
          return newLogs;
        });
      } catch (e) {
        // Fallback for raw text logs
        setLogs((prev) => [...prev, {
          timestamp: new Date().toISOString(),
          level: 'INFO',
          process: 'UNKNOWN',
          message: event.data,
          logger: ''
        }]);
      }
    };

    ws.current.onerror = (err) => {
      console.error('WebSocket Error:', err);
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  const displayedLogs = hideSql
    ? logs.filter((l) => !isSqlLog(l.message, l.logger))
    : logs;

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [displayedLogs, autoScroll]);

  const clearLogs = () => setLogs([]);

  const downloadLogs = () => {
    const text = displayedLogs.map(l => `[${l.timestamp}] [${l.process}] [${l.level}] ${l.message}`).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `system-logs-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getLogColor = (level: string) => {
    switch (level) {
      case 'ERROR':
      case 'CRITICAL':
        return 'text-red-400';
      case 'WARNING':
        return 'text-yellow-400';
      case 'DEBUG':
        return 'text-gray-500';
      default:
        return 'text-blue-300';
    }
  };

  const getProcessColor = (process: string) => {
    if (process === 'API') return 'text-purple-400';
    if (process === 'WORKER') return 'text-cyan-400';
    return 'text-gray-400';
  };

  return (
    <div className="flex flex-col h-full w-full max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-500/10 rounded-lg border border-blue-500/20">
            <FiTerminal className="w-6 h-6 text-blue-400" />
          </div>
          <h2 className="text-3xl font-bold text-white tracking-tight">System Logs</h2>
          
          <div className="ml-4 flex items-center space-x-2">
            <span className="relative flex h-3 w-3">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isPaused ? 'bg-yellow-400' : 'bg-green-400'}`}></span>
              <span className={`relative inline-flex rounded-full h-3 w-3 ${isPaused ? 'bg-yellow-500' : 'bg-green-500'}`}></span>
            </span>
            <span className="text-sm font-medium text-gray-400">
              {isPaused ? 'Paused' : 'Streaming live...'}
            </span>
          </div>
        </div>

        <div className="flex space-x-3">
          <label className="flex items-center space-x-2 text-sm text-gray-300 mr-2 cursor-pointer bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg border border-white/10 transition-colors">
            <input 
              type="checkbox" 
              checked={hideSql} 
              onChange={(e) => setHideSql(e.target.checked)} 
              className="rounded bg-black/50 border-gray-600 text-blue-500 focus:ring-blue-500/50 cursor-pointer"
            />
            <span className="text-xs font-semibold text-blue-300">Bỏ qua SQL</span>
          </label>
          <label className="flex items-center space-x-2 text-sm text-gray-300 mr-4 cursor-pointer">
            <input 
              type="checkbox" 
              checked={autoScroll} 
              onChange={(e) => setAutoScroll(e.target.checked)} 
              className="rounded bg-black/50 border-gray-600 text-blue-500 focus:ring-blue-500/50"
            />
            <span>Auto-scroll</span>
          </label>
          <button
            onClick={() => setIsPaused(!isPaused)}
            className="flex items-center space-x-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors text-sm font-medium"
          >
            {isPaused ? <FiPlay className="w-4 h-4" /> : <FiPause className="w-4 h-4" />}
            <span>{isPaused ? 'Resume' : 'Pause'}</span>
          </button>
          <button
            onClick={downloadLogs}
            className="flex items-center space-x-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors text-sm font-medium"
          >
            <FiDownload className="w-4 h-4" />
            <span>Export</span>
          </button>
          <button
            onClick={clearLogs}
            className="flex items-center space-x-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg transition-colors text-sm font-medium"
          >
            <FiTrash2 className="w-4 h-4" />
            <span>Clear</span>
          </button>
        </div>
      </div>

      <div className="flex-1 bg-[#050508] border border-white/10 rounded-xl overflow-hidden shadow-2xl relative flex flex-col font-mono text-sm">
        {/* Terminal Header */}
        <div className="h-8 bg-white/5 border-b border-white/10 flex items-center px-4 space-x-2">
          <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
          <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
          <span className="text-xs text-gray-500 ml-2">bash - system_logs</span>
        </div>

        {/* Terminal Body */}
        <div className="flex-1 overflow-auto p-4 space-y-1">
          {displayedLogs.length === 0 ? (
            <div className="text-gray-500 italic">Waiting for log events...</div>
          ) : (
            displayedLogs.map((log, i) => (
              <div key={i} className="hover:bg-white/5 px-2 py-0.5 rounded flex break-all">
                <span className="text-gray-600 mr-3 shrink-0">
                  {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, fractionalSecondDigits: 3 })}
                </span>
                <span className={`font-semibold mr-3 w-16 shrink-0 ${getProcessColor(log.process)}`}>
                  [{log.process}]
                </span>
                <span className={`font-bold mr-3 w-12 shrink-0 ${getLogColor(log.level)}`}>
                  {log.level}
                </span>
                <span className="text-gray-300">
                  {log.message}
                </span>
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
}
