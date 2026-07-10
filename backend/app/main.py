"""
FastAPI main application — WebSocket streaming, REST endpoints, and pipeline orchestration.
"""

import os
import shutil
import asyncio
import json
import logging
import threading
import time
import queue
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .inference import ViolenceDetector
from .video_stream import VideoStream
from .smoothing import TemporalSmoother
from .alert import AlertManager
from .utils import get_timestamp, get_readable_timestamp

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Global State ──────────────────────────────────────────────────────
detector = ViolenceDetector()
video_stream = VideoStream()
smoother = TemporalSmoother()
alert_manager = AlertManager()

# Directory for uploaded videos
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Connected WebSocket clients
ws_clients: set[WebSocket] = set()
ws_clients_lock = threading.Lock()

# Pipeline control
pipeline_running = False
inference_thread: threading.Thread | None = None
result_queue: queue.Queue = queue.Queue()
broadcaster_task: asyncio.Task | None = None

# Latest result for new clients
latest_result: dict | None = None


# ── Lifespan ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global broadcaster_task
    
    logger.info("=" * 60)
    logger.info("Violence Detection System — Starting Up")
    logger.info("=" * 60)

    # Start results broadcaster task
    broadcaster_task = asyncio.create_task(result_broadcaster())
    
    # Load model at startup
    if detector.load():
        logger.info("✅ Transformers model loaded successfully")
    else:
        logger.warning("⚠️  Model not found or failed to load — inference will use mock scores")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if broadcaster_task:
        broadcaster_task.cancel()
    stop_pipeline()
    logger.info("Goodbye!")



app = FastAPI(
    title="Violence Detection API",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Inference Pipeline (runs in background thread) ───────────────────
def inference_loop():
    """
    Background inference thread.
    Reads frame buffers, runs ONNX model, smooths scores,
    sends results to WebSocket clients, and triggers SMS alerts.
    """
    global pipeline_running, latest_result
    logger.info("🔄 Inference thread started")

    while pipeline_running:
        # Get frames from buffer
        frames, buffer_timestamp = video_stream.get_inference_buffer()

        if frames is None:
            # If the video stream is stopped and we can't extract any more frames, we're completely done
            if not video_stream.is_running:
                logger.info("🎬 Video stream finished and all frames processed, stopping pipeline")
                result_queue.put({"type": "status", "event": "pipeline_finished"})
                stop_pipeline()
                break

            if video_stream.buffer_size < settings.WINDOW_SIZE:
                if int(time.time()) % 5 == 0:
                    logger.debug(f"Buffer filling: {video_stream.buffer_size}/{settings.WINDOW_SIZE}")
            time.sleep(0.01)
            continue

        try:
            # Run inference
            if detector.is_loaded:
                prediction = detector.predict(frames)
                raw_score = prediction["violence_score"]
            else:
                # Mock score for testing without model
                import random
                raw_score = random.uniform(0.1, 0.5)

            # Temporal smoothing
            smooth_result = smoother.update(raw_score)

            # Build result payload
            result = {
                "timestamp": float(buffer_timestamp),
                "score": smooth_result["smoothed_score"],
                "raw_score": smooth_result["raw_score"],
                "is_violence": smooth_result["is_violence"],
                "scores_above_threshold": smooth_result["scores_above_threshold"],
            }

            latest_result = result

            logger.info(
                f"Score: {result['score']:.3f} | "
                f"Raw: {result['raw_score']:.3f} | "
                f"Violence: {'🔴 YES' if result['is_violence'] else '🟢 NO'}"
            )

            # Queue for WebSocket broadcasting (thread-safe)
            result_queue.put(result)
            logger.info(f"AI Score: {result['score']:.4f} | Violence: {'🔴' if result['is_violence'] else '🟢'}")

            # Trigger SMS alert if violence detected
            if smooth_result["is_violence"]:
                alert_manager.send_alert(get_readable_timestamp())

        except Exception as e:
            logger.error(f"Inference error: {e}", exc_info=True)
            time.sleep(0.1)

    logger.info("Inference thread stopped")


async def result_broadcaster():
    """Background task to broadcast results from the queue."""
    logger.info("📡 Results broadcaster started")
    loop = asyncio.get_running_loop()
    
    while True:
        try:
            # Use run_in_executor to wait for the thread-safe queue without blocking the event loop
            result = await loop.run_in_executor(None, result_queue.get)
            await broadcast(json.dumps(result))
            result_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Broadcaster error: {e}")
            await asyncio.sleep(0.1)


async def broadcast(message: str):
    """Send a message to all connected WebSocket clients."""
    disconnected = []
    with ws_clients_lock:
        clients = list(ws_clients)
    
    if clients:
        # logger.debug(f"Broadcasting to {len(clients)} clients")
        pass

    for client in clients:
        try:
            await client.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send to client {client.client}: {e}")
            disconnected.append(client)

    if disconnected:
        with ws_clients_lock:
            for c in disconnected:
                ws_clients.discard(c)


def start_pipeline(source=None):
    """Start the video capture and inference pipeline."""
    global pipeline_running, inference_thread

    if pipeline_running:
        logger.warning("Pipeline already running")
        return False

    # Reset smoother
    smoother.reset()

    # Start video capture
    logger.info(f"Starting pipeline with source: {source or settings.VIDEO_SOURCE}")
    if source is not None:
        video_stream.source = source
    elif source is None and not video_stream.is_running:
        pass  # Use default source from config

    if not video_stream.start():
        logger.error("Failed to start video stream")
        return False

    # Start inference thread
    pipeline_running = True
    inference_thread = threading.Thread(
        target=inference_loop, daemon=True, name="InferenceThread"
    )
    inference_thread.start()
    logger.info("🚀 Pipeline started")
    return True


def stop_pipeline():
    """Stop the video capture and inference pipeline."""
    global pipeline_running, inference_thread

    if not pipeline_running and not video_stream.is_running:
        return

    pipeline_running = False
    video_stream.stop()

    # Avoid deadlock if calling from the inference thread itself
    if inference_thread and inference_thread.is_alive() and threading.current_thread() != inference_thread:
        inference_thread.join(timeout=2.0)
    
    inference_thread = None
    logger.info("🛑 Pipeline stopped")


# ── REST Endpoints ────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": detector.is_loaded,
        "pipeline_running": pipeline_running,
        "twilio_enabled": alert_manager.is_enabled,
    }


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file for processing."""
    file_path = UPLOAD_DIR / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "filename": file.filename,
        "path": str(file_path.absolute()),
        "message": "File uploaded successfully"
    }


@app.get("/api/video_feed")
async def video_feed():
    """Video streaming route. Returns MJPEG stream."""
    if not video_stream.is_running:
        # Auto-start if not running (with default source)
        start_pipeline()
        
    return StreamingResponse(
        video_stream.generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.post("/api/start")
async def start(source: str = Query(default=None)):
    """Start the detection pipeline. Optional source: '0' for webcam or file path."""
    logger.info(f"API: Received start request with source: {source}")
    parsed_source = None
    if source is not None:
        try:
            parsed_source = int(source)
        except ValueError:
            parsed_source = source

    success = start_pipeline(parsed_source)
    return {"started": success, "source": str(parsed_source or settings.VIDEO_SOURCE)}


@app.post("/api/stop")
async def stop():
    """Stop the detection pipeline."""
    logger.info("API: Received stop request")
    stop_pipeline()
    return {"stopped": True}


@app.get("/api/status")
async def status():
    return {
        "pipeline_running": pipeline_running,
        "model_loaded": detector.is_loaded,
        "buffer_size": video_stream.buffer_size,
        "latest_result": latest_result,
        "connected_clients": len(ws_clients),
    }


# ── WebSocket Endpoint ───────────────────────────────────────────────
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time violence detection results.
    Sends JSON: { timestamp, score, is_violence }
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected: {websocket.client}")

    with ws_clients_lock:
        ws_clients.add(websocket)

    try:
        # Send latest result if available
        if latest_result:
            await websocket.send_text(json.dumps(latest_result))

        # Keep connection alive
        while True:
            # Wait for any client messages (ping/pong or commands)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle client commands
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send keepalive
                try:
                    await websocket.send_text(json.dumps({"type": "keepalive"}))
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        with ws_clients_lock:
            ws_clients.discard(websocket)
