import axios from 'axios';

const API_BASE = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
});

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  pipeline_running: boolean;
  twilio_enabled: boolean;
}

export interface StatusResponse {
  pipeline_running: boolean;
  model_loaded: boolean;
  buffer_size: number;
  latest_result: {
    timestamp: string;
    score: number;
    is_violence: boolean;
  } | null;
  connected_clients: number;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await api.get<HealthResponse>('/api/health');
  return res.data;
}

export async function getStatus(): Promise<StatusResponse> {
  const res = await api.get<StatusResponse>('/api/status');
  return res.data;
}

export async function uploadVideo(file: File): Promise<{ filename: string; path: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await api.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function startDetection(source?: string): Promise<{ started: boolean; source: string }> {
  const params = source !== undefined ? { source } : {};
  const res = await api.post('/api/start', null, { params });
  return res.data;
}

export async function stopDetection(): Promise<{ stopped: boolean }> {
  const res = await api.post('/api/stop');
  return res.data;
}

export default api;
