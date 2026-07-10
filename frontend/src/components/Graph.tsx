import { useEffect, useState, useRef, useCallback } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { DetectionResult } from '../hooks/useWebSocket';
import './Graph.css';

interface GraphProps {
  bufferRef: React.MutableRefObject<DetectionResult[]>;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  isProcessing: boolean;
  threshold?: number;
  onViolenceChange?: (isViolence: boolean, score: number) => void;
}

// How many seconds of video to show before scrolling
const TIME_WINDOW = 30;

interface PlotPoint {
  time: number;        // video timestamp (seconds) — when this 16-frame clip ends
  score: number;       // confidence score 0–100
  isViolence: boolean;
}

export default function Graph({ bufferRef, videoRef, isProcessing, threshold = 0.7, onViolenceChange }: GraphProps) {
  const [graphData, setGraphData] = useState<PlotPoint[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);
  const rafRef = useRef<number | null>(null);
  // Stores ALL prediction points (even those ahead of video)
  const allPointsRef = useRef<PlotPoint[]>([]);
  const builtCountRef = useRef(0);

  // Runs every frame: rebuild points if new clips, then filter by video time
  const updateGraph = useCallback(() => {
    const video = videoRef.current;
    const now = video ? video.currentTime : 0;
    setCurrentTime(now);

    if (video) {
      const dur = video.duration;
      if (isFinite(dur) && dur > 0) {
        setVideoDuration(dur);
      }
    }

    const allClips = bufferRef.current;

    if (allClips.length === 0) {
      if (builtCountRef.current !== 0) {
        allPointsRef.current = [];
        builtCountRef.current = 0;
        setGraphData([]);
      }
      return;
    }

    // Rebuild full points array only when new clips arrive
    if (allClips.length !== builtCountRef.current) {
      builtCountRef.current = allClips.length;
      allPointsRef.current = allClips.map((clip) => ({
        time: parseFloat(clip.timestamp.toFixed(2)),
        score: parseFloat((clip.score * 100).toFixed(1)),
        isViolence: clip.is_violence,
      }));
    }

    // ── Generate one data point per second up to video.currentTime ──
    // If there's no prediction at that second, carry forward the previous score.
    // This creates a smooth line across the full timeline.
    const predictions = allPointsRef.current;
    const maxSec = Math.floor(now);
    const perSecond: PlotPoint[] = [];
    let lastScore = 0;
    let lastViolence = false;

    for (let t = 0; t <= maxSec; t++) {
      // Find the latest prediction at or before this second
      let bestIdx = -1;
      for (let i = predictions.length - 1; i >= 0; i--) {
        if (predictions[i].time <= t + 0.99) {
          bestIdx = i;
          break;
        }
      }

      if (bestIdx >= 0) {
        lastScore = predictions[bestIdx].score;
        lastViolence = predictions[bestIdx].isViolence;
      }

      perSecond.push({
        time: t,
        score: lastScore,
        isViolence: lastViolence,
      });
    }

    setGraphData(perSecond);
  }, [bufferRef, videoRef]);

  // Animation frame loop for real-time updates
  useEffect(() => {
    let running = true;
    function loop() {
      if (!running) return;
      updateGraph();
      rafRef.current = requestAnimationFrame(loop);
    }
    if (isProcessing || bufferRef.current.length > 0) {
      rafRef.current = requestAnimationFrame(loop);
    }
    return () => {
      running = false;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [isProcessing, updateGraph, bufferRef]);

  // Keep loop alive on play/seek after processing stops
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const restart = () => {
      if (bufferRef.current.length > 0 && rafRef.current === null) {
        let running = true;
        function loop() {
          if (!running) return;
          updateGraph();
          rafRef.current = requestAnimationFrame(loop);
        }
        rafRef.current = requestAnimationFrame(loop);
        video.addEventListener('pause', () => { running = false; }, { once: true });
      }
      updateGraph();
    };
    video.addEventListener('play', restart);
    video.addEventListener('seeked', restart);
    return () => {
      video.removeEventListener('play', restart);
      video.removeEventListener('seeked', restart);
    };
  }, [videoRef, bufferRef, updateGraph]);

  const latestPoint = graphData.length > 0 ? graphData[graphData.length - 1] : null;
  const currentScore = latestPoint?.score ?? 0;
  // Determine violence from graph score vs threshold — this is synced to video time
  const isCurrentViolence = currentScore > (threshold * 100);

  // Report violence state to parent — only fires when graph crosses threshold
  useEffect(() => {
    if (onViolenceChange) {
      onViolenceChange(isCurrentViolence, currentScore / 100);
    }
  }, [isCurrentViolence, currentScore, onViolenceChange]);

  // X-axis = video duration + 5 seconds buffer (e.g., 35 for a 30s video)
  const xMax = videoDuration > 0 ? Math.ceil(videoDuration) + 5 : TIME_WINDOW;

  const thresholdPct = threshold * 100;

  return (
    <div className="graph-card">
      <div className="graph-header">
        <div className="graph-title">
          <span className="graph-icon">📊</span>
          Violence Detection — Real-Time
        </div>
        <div className="graph-stats">
          <div className="clip-counter">
            Predictions: {builtCountRef.current}
          </div>
          <div className="graph-time">{currentTime.toFixed(1)}s</div>
          <div className={`current-score ${isCurrentViolence ? 'danger' : 'safe'}`}>
            {currentScore.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="graph-container">
        {graphData.length === 0 && !isProcessing && bufferRef.current.length === 0 ? (
          <div className="graph-empty">
            <span className="empty-icon">⏳</span>
            <p>Waiting for predictions...</p>
          </div>
        ) : graphData.length === 0 ? (
          <div className="graph-empty">
            <span className="empty-icon">🔄</span>
            <p>Processing... {bufferRef.current.length > 0 ? `${bufferRef.current.length} clips ready` : 'awaiting first clip'}</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={graphData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.06)"
              />

              {/* X-axis: Video Timestamp */}
              <XAxis
                dataKey="time"
                stroke="#4a4f6a"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                tickFormatter={(val: number) => {
                  const mins = Math.floor(val / 60);
                  const secs = (val % 60).toFixed(1);
                  return mins > 0 ? `${mins}:${Math.floor(val % 60).toString().padStart(2, '0')}` : `${secs}s`;
                }}
                domain={[0, xMax]}
                type="number"
                allowDataOverflow={false}
                label={{ value: 'Video Time (s)', position: 'insideBottomRight', offset: -5, fill: '#6b7280', fontSize: 10 }}
              />

              {/* Y-axis: Confidence Score 0–100 */}
              <YAxis
                domain={[0, 100]}
                stroke="#4a4f6a"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                ticks={[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]}
                tickFormatter={(v: number) => `${v}`}
                label={{ value: 'Confidence Score', angle: -90, position: 'insideLeft', offset: 10, fill: '#6b7280', fontSize: 10 }}
              />

              {/* Tooltip on hover */}
              <Tooltip
                contentStyle={{
                  background: 'rgba(20, 22, 35, 0.95)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
                }}
                labelStyle={{ color: '#8890a8', fontSize: 11, marginBottom: 4 }}
                itemStyle={{ color: '#e0e4f0', fontSize: 13, fontWeight: 600 }}
                formatter={(value: number) => [`${value.toFixed(1)}%`, 'Score']}
                labelFormatter={(label: number) => {
                  const mins = Math.floor(label / 60);
                  const secs = (label % 60).toFixed(1);
                  return mins > 0 ? `Video @ ${mins}:${parseFloat(secs).toFixed(0).padStart(2, '0')}` : `Video @ ${secs}s`;
                }}
              />

              {/* Threshold line at 70% */}
              <ReferenceLine
                y={thresholdPct}
                stroke="#ef4444"
                strokeDasharray="6 3"
                strokeWidth={1.5}
                label={{
                  value: `Threshold (${thresholdPct}%)`,
                  position: 'insideTopRight',
                  fill: '#ef4444',
                  fontSize: 10,
                  fontWeight: 600,
                }}
              />

              {/* Line connecting all prediction dots */}
              <Line
                type="monotone"
                dataKey="score"
                stroke="#6366f1"
                strokeWidth={2}
                isAnimationActive={false}
                dot={(props: any) => {
                  const { cx, cy, payload } = props;
                  // Red dot if violence, blue dot if normal
                  return (
                    <circle
                      key={`dot-${payload.time}`}
                      cx={cx}
                      cy={cy}
                      r={4}
                      fill={payload.isViolence ? '#ef4444' : '#6366f1'}
                      stroke="#fff"
                      strokeWidth={1.5}
                    />
                  );
                }}
                activeDot={{ r: 6, fill: '#6366f1', stroke: '#fff', strokeWidth: 2 }}
              />

              {/* ▶ Now — vertical playhead tracking video.currentTime */}
              <ReferenceLine
                x={parseFloat(currentTime.toFixed(2))}
                stroke="#22d3ee"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                label={{
                  value: `▶ ${currentTime.toFixed(1)}s`,
                  position: 'insideTopLeft',
                  fill: '#22d3ee',
                  fontSize: 9,
                  fontWeight: 600,
                }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="graph-footer">
        <div className="legend-item"><span className="legend-dot" style={{ background: '#6366f1' }}></span>Normal</div>
        <div className="legend-item"><span className="legend-dot" style={{ background: '#ef4444' }}></span>Violence</div>
        <div className="legend-item"><span className="legend-line threshold-line"></span>Threshold ({thresholdPct}%)</div>
        <div className="legend-item"><span className="legend-line now-line"></span>Playback</div>
      </div>
    </div>
  );
}
