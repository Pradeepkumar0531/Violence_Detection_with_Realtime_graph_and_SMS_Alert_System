import { useState, useEffect, useRef, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import VideoPlayer from '../components/VideoPlayer';
import Graph from '../components/Graph';
import AlertBanner from '../components/AlertBanner';
import { getHealth, startDetection, stopDetection, uploadVideo } from '../services/api';
import type { HealthResponse } from '../services/api';
import './Dashboard.css';

export default function Dashboard() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const { bufferRef, latestResult, connected, status, clearBuffer, connect, disconnect } = useWebSocket();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'webcam' | 'file'>('webcam');
  const [videoSource, setVideoSource] = useState('0');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [localVideoUrl, setLocalVideoUrl] = useState<string | null>(null);

  // Violence state driven by the GRAPH (synced to video playhead)
  const [graphViolence, setGraphViolence] = useState(false);
  const [graphScore, setGraphScore] = useState(0);

  const onGraphViolenceChange = useCallback((isViolence: boolean, score: number) => {
    setGraphViolence(isViolence);
    setGraphScore(score);
  }, []);

  // Auto-stop UI when pipeline finishes (from WebSocket)
  useEffect(() => {
    if (status?.event === 'pipeline_finished') {
      console.log('Pipeline finished from WebSocket');
      if (mode === 'webcam') {
        setPipelineRunning(false);
        disconnect();
      }
    }
  }, [status, mode, disconnect]);

  // Fetch health on mount
  useEffect(() => {
    async function fetchHealth() {
      try {
        const h = await getHealth();
        setHealth(h);
        
        setPipelineRunning((prev) => {
          if (mode === 'file' && prev === true && h.pipeline_running === false) {
             return true;
          }
          return h.pipeline_running;
        });
        
      } catch {
        console.warn('Backend not reachable');
      }
    }
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, [mode]);

  const handleStart = async (sourceOverride?: string) => {
    setLoading(true);
    clearBuffer(); 
    try {
      const source = sourceOverride || (mode === 'webcam' ? videoSource : null);
      if (source === null) {
        alert("Please upload a file first");
        setLoading(false);
        return;
      }
      
      connect();
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const res = await startDetection(source);
      setPipelineRunning(res.started);
      if (!res.started) {
        alert("Failed to start detection.");
      }
    } catch (err) {
      console.error('Failed to start:', err);
    }
    setLoading(false);
  };

  const handleStop = async (preserveBuffer = false) => {
    setLoading(true);
    try {
      await stopDetection();
      setPipelineRunning(false);
      disconnect();
      if (!preserveBuffer) {
        // Only clear buffer on explicit user stop, not on video end
      }
    } catch {
      alert("Failed to stop pipeline");
    }
    setLoading(false);
  };

  // Called when video finishes — stop pipeline but keep graph data
  const handleVideoEnded = () => {
    console.log('[DASHBOARD] Video ended — stopping pipeline, preserving graph');
    handleStop(true);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setLocalVideoUrl(URL.createObjectURL(file));
    }
  };

  const handleUploadAndStart = async () => {
    if (!selectedFile) return;
    setLoading(true);
    try {
      const uploadRes = await uploadVideo(selectedFile);
      await handleStart(uploadRes.path);
    } catch (err) {
      console.error('Upload failed:', err);
      alert('Failed to upload video');
    }
    setLoading(false);
  };



  return (
    <div className="dashboard">
      <AlertBanner isViolence={graphViolence} score={graphScore} />

      <header className="dashboard-header">
        <div className="header-left">
          <h1 className="app-title">
            <span className="title-icon">🛡️</span>
            Violence Detection <span className="badge">PRO</span>
          </h1>
          <p className="app-subtitle">Real-Time Surveillance AI</p>
        </div>

        <div className="connection-status">
          <span className={`status-icon ${connected ? 'connected' : 'disconnected'}`}></span>
          {connected ? 'Cloud Connected' : 'Connecting...'}
        </div>
      </header>

      <div className="mode-selector">
        <button 
          className={`mode-btn ${mode === 'webcam' ? 'active' : ''}`}
          onClick={() => { setMode('webcam'); setLocalVideoUrl(null); }}
          disabled={pipelineRunning}
        >
          📹 Live Webcam
        </button>
        <button 
          className={`mode-btn ${mode === 'file' ? 'active' : ''}`}
          onClick={() => { setMode('file'); }}
          disabled={pipelineRunning}
        >
          📁 Video Upload
        </button>
      </div>

      <div className="control-bar">
        {mode === 'webcam' ? (
          <div className="control-section">
            <div className="source-input-group">
              <label className="source-label">Webcam Index</label>
              <input
                type="text"
                className="source-input"
                value={videoSource}
                onChange={(e) => setVideoSource(e.target.value)}
                disabled={pipelineRunning}
              />
            </div>
            <div className="control-buttons">
              {!pipelineRunning ? (
                <button className="btn btn-start" onClick={() => handleStart()} disabled={loading}>
                  {loading ? '⏳...' : '▶ Start Webcam'}
                </button>
              ) : (
                <button className="btn btn-stop" onClick={handleStop} disabled={loading}>
                  ⏹ Stop Pipeline
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="control-section">
            <div className="source-input-group">
              <label className="source-label">Select Video</label>
              <input
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                className="file-input"
                disabled={pipelineRunning}
              />
            </div>
            <div className="control-buttons">
              {!pipelineRunning ? (
                <button className="btn btn-upload" onClick={handleUploadAndStart} disabled={loading || !selectedFile}>
                  {loading ? '⏳...' : '⬆ Process Video'}
                </button>
              ) : (
                <button className="btn btn-stop" onClick={handleStop} disabled={loading}>
                  ⏹ Stop Processing
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="dashboard-grid">
        <div className="grid-video">
          <VideoPlayer
            ref={videoRef}
            isViolence={graphViolence}
            score={graphScore}
            videoUrl={localVideoUrl}
            isStreaming={pipelineRunning && mode === 'webcam'}
            isProcessing={pipelineRunning}
            latestPredictionTime={latestResult?.timestamp ?? null}
            onEnded={() => {
              if (pipelineRunning) handleVideoEnded();
            }}
          />
        </div>
        <div className="grid-graph">
          <Graph 
            bufferRef={bufferRef} 
            videoRef={videoRef} 
            isProcessing={pipelineRunning}
            threshold={0.7}
            onViolenceChange={onGraphViolenceChange}
          />
        </div>
      </div>

      <div className="stats-bar-footer">
        <div className="stat-card">
          <div className="stat-value">{bufferRef.current.length}</div>
          <div className="stat-label">Inferences</div>
        </div>
        <div className="stat-card">
          <div className={`stat-value ${graphViolence ? 'text-danger' : 'text-safe'}`}>
            {(graphScore * 100).toFixed(1)}%
          </div>
          <div className="stat-label">Current Score</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">
            {bufferRef.current.filter(s => s.is_violence).length}
          </div>
          <div className="stat-label">Alerts Triggered</div>
        </div>
        <div className="stat-card">
          <div className={`stat-value ${pipelineRunning ? 'text-safe' : ''}`}>
            {pipelineRunning ? 'Active' : 'Idle'}
          </div>
          <div className="stat-label">Pipeline Status</div>
        </div>
      </div>
    </div>
  );
}
