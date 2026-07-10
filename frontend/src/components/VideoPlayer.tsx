import React, { useEffect, useRef, useState } from 'react';
import './VideoPlayer.css';

interface VideoPlayerProps {
  isViolence: boolean;
  score: number | null;
  videoUrl?: string | null;
  isStreaming?: boolean;
  isProcessing?: boolean;
  onEnded?: () => void;
  onTimeUpdate?: (time: number) => void;
  latestPredictionTime?: number | null;
}

const VideoPlayer = React.forwardRef<HTMLVideoElement, VideoPlayerProps>(({ 
  isViolence, score, videoUrl, isStreaming, isProcessing, onEnded, onTimeUpdate, latestPredictionTime
}, ref) => {
  const internalRef = useRef<HTMLVideoElement>(null);
  const videoRef = (ref as React.MutableRefObject<HTMLVideoElement>) || internalRef;
  const [cameraActive, setCameraActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Handle source changes
  useEffect(() => {
    if (videoUrl && videoRef.current) {
      setCameraActive(false);
      videoRef.current.srcObject = null;
      if (!videoRef.current.src.includes(videoUrl)) {
        videoRef.current.src = videoUrl;
      }
    }
  }, [videoUrl, videoRef]);

  // Handle playback control independently
  useEffect(() => {
    if (videoUrl && videoRef.current) {
      if (isProcessing) {
        videoRef.current.play().catch(e => console.error("Video play error:", e));
      } else {
        videoRef.current.pause();
      }
    }
  }, [isProcessing, videoUrl, videoRef]);

  // ── Adaptive playback rate: sync video with backend predictions ────
  useEffect(() => {
    if (!videoUrl || !isProcessing || !videoRef.current) return;
    const video = videoRef.current;

    const adjustRate = () => {
      if (!video || video.paused) return;

      // No predictions yet — slow down so backend can fill initial buffer
      if (latestPredictionTime == null || latestPredictionTime <= 0) {
        video.playbackRate = 0.4;
        return;
      }

      const ahead = video.currentTime - latestPredictionTime;

      if (ahead > 3) {
        // Video is way ahead — slow down significantly
        video.playbackRate = 0.3;
      } else if (ahead > 1.5) {
        // Slightly ahead — gentle slowdown
        video.playbackRate = 0.5;
      } else {
        // Synced or behind predictions — normal speed
        video.playbackRate = 1.0;
      }
    };

    const interval = setInterval(adjustRate, 300);
    adjustRate();

    return () => {
      clearInterval(interval);
      if (video) video.playbackRate = 1.0;
    };
  }, [isProcessing, latestPredictionTime, videoUrl, videoRef]);

  // Handle webcam stream
  useEffect(() => {
    if (videoUrl) return; // Skip if file mode

    if (!isStreaming) {
      setCameraActive(false);
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach(track => track.stop());
        videoRef.current.srcObject = null;
      }
      return;
    }

    let stream: MediaStream | null = null;

    const startCamera = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ 
          video: { width: 1280, height: 720 },
          audio: false 
        });
        
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();
          setCameraActive(true);
          setError(null);
        }
      } catch (err) {
        console.error("Camera error:", err);
        setError("Could not access camera. Please check permissions.");
        setCameraActive(false);
      }
    };

    startCamera();

    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [videoUrl, isStreaming, isProcessing, videoRef]);

  return (
    <div className={`video-player ${isViolence ? 'violence-detected' : ''}`}>
      <div className="video-header">
        <div className="video-title">
          <span className="camera-icon">{videoUrl ? '🎬' : '📹'}</span>
          {videoUrl ? 'Video' : 'Live Camera Feed'}
        </div>
        <div className={`status-dot ${cameraActive ? 'active' : videoUrl ? 'active' : 'inactive'}`}>
          <span className="dot"></span>
          {cameraActive ? 'LIVE' : videoUrl ? 'FILE' : 'OFFLINE'}
        </div>
      </div>

      <div className="video-container">
        {error ? (
          <div className="video-error">
            <span className="error-icon">⚠️</span>
            <p>{error}</p>
          </div>
        ) : isStreaming ? (
          <img
            src="http://localhost:8000/api/video_feed"
            className="video-feed"
            alt="Live Stream"
          />
        ) : videoUrl ? (
          <video
            ref={videoRef}
            playsInline
            muted
            loop={false}
            className="video-feed"
            onEnded={onEnded}
            onTimeUpdate={() => {
              if (videoRef.current && onTimeUpdate) {
                onTimeUpdate(videoRef.current.currentTime);
              }
            }}
          />
        ) : (
          <div className="video-error">
            <span className="error-icon">🔌</span>
            <p>System Offline</p>
          </div>
        )}
      </div>
      
      {isViolence && (
        <div className="violence-overlay">
          ⚠️ VIOLENCE DETECTED
        </div>
      )}
    </div>
  );
});

export default VideoPlayer;
