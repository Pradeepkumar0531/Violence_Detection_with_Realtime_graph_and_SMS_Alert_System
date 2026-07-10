import { useEffect, useState } from 'react';
import './AlertBanner.css';

interface AlertBannerProps {
  isViolence: boolean;
  score: number | null;
  autoHideDelay?: number;
}

export default function AlertBanner({
  isViolence,
  score,
  autoHideDelay = 5000,
}: AlertBannerProps) {
  const [visible, setVisible] = useState(false);
  const [lastTriggerTime, setLastTriggerTime] = useState<string>('');

  useEffect(() => {
    if (isViolence) {
      // Violence is active — show banner
      setVisible(true);
      setLastTriggerTime(
        new Date().toLocaleTimeString('en-US', {
          hour12: true,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    } else {
      // Violence ended — hide banner immediately
      setVisible(false);
    }
  }, [isViolence]);

  if (!visible) return null;

  return (
    <div className="alert-banner" role="alert">
      <div className="alert-content">
        <div className="alert-icon-wrapper">
          <span className="alert-icon">🚨</span>
        </div>
        <div className="alert-text">
          <div className="alert-title">Violence Detected</div>
          <div className="alert-detail">
            Confidence: {score !== null ? `${(score * 100).toFixed(1)}%` : 'N/A'}
            {lastTriggerTime && <span className="alert-time"> · {lastTriggerTime}</span>}
          </div>
        </div>
        <button className="alert-dismiss" onClick={() => setVisible(false)}>
          ✕
        </button>
      </div>
    </div>
  );
}
