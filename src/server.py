from __future__ import annotations

import asyncio
import json
from pathlib import Path
import os
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .organizer import MusicOrganizer
import httpx


def create_app(organizer: MusicOrganizer) -> FastAPI:
    # Shutdown signal for long-lived streams (e.g., SSE) to terminate promptly on reload
    shutdown_event: asyncio.Event = asyncio.Event()

    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        # Startup: enqueue initial scan job if DB empty
        try:
            counts = organizer.jobstore.counts()
            total_existing = sum(counts.values())
            if total_existing == 0:
                organizer.jobstore.enqueue(
                    organizer.source_dir,
                    {"type": "scan", "root": str(organizer.source_dir)},
                    job_type="scan",
                )
        except Exception:
            pass
        try:
            yield
        finally:
            shutdown_event.set()

    app = FastAPI(title="What's That Sound API", lifespan=app_lifespan)
    # CORS for local Vite dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Staged (unapplied) path changes
    staged_source: Optional[Path] = None
    staged_target: Optional[Path] = None



    # Frontend is served by Vite in development. In production, we will mount the built assets
    # after declaring API routes so that /api/* is not intercepted by the static mount.

    @app.get("/api/status")
    def status():
        counts = organizer.jobstore.counts()
        ready = organizer.jobstore.fetch_ready(limit=200)
        stats = organizer.progress_tracker.get_stats()
        return {
            "source_dir": str(organizer.source_dir),
            "target_dir": str(organizer.target_dir),
            "counts": counts,
            "processed": stats.get("total_processed", 0),
            "total": len(list(organizer.source_dir.iterdir())),
            "ready": [{"path": fp, "name": Path(fp).name} for _, fp, _ in ready],
        }

    @app.get("/api/paths")
    def get_paths():
        return {
            "current": {"source_dir": str(organizer.source_dir), "target_dir": str(organizer.target_dir)},
            "staged": {
                "source_dir": str(staged_source) if staged_source else "",
                "target_dir": str(staged_target) if staged_target else "",
            },
        }

    @app.post("/api/paths")
    def post_paths(payload: Dict[str, Any]):
        nonlocal staged_source, staged_target
        src = payload.get("source_dir")
        dst = payload.get("target_dir")
        action = payload.get("action") or "stage"
        if action == "stage":
            if src is not None:
                staged_source = Path(src)
            if dst is not None:
                staged_target = Path(dst)
            return {"ok": True}
        if action == "cancel":
            staged_source = None
            staged_target = None
            return {"ok": True}
        if action == "confirm":
            new_source = staged_source or organizer.source_dir
            new_target = staged_target or organizer.target_dir
            # Apply paths
            organizer.update_paths(new_source, new_target)
            # Enqueue a scan job for new source
            try:
                organizer.jobstore.enqueue(organizer.source_dir, {"type": "scan", "root": str(organizer.source_dir)}, job_type="scan")
            finally:
                staged_source = None
                staged_target = None
            return {"ok": True}
        raise HTTPException(400, "invalid action")

    @app.get("/api/list")
    def list_dirs(path: str):
        base = Path(path)
        if not base.exists():
            raise HTTPException(404, "path not found")
        if not base.is_dir():
            raise HTTPException(400, "not a directory")
        try:
            entries = []
            for p in sorted([d for d in base.iterdir() if d.is_dir()]):
                entries.append({"name": p.name, "path": str(p)})
            parent = str(base.parent) if base.parent != base else ""
            return {"entries": entries, "parent": parent}
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.get("/api/ready")
    def ready(limit: int = 50):
        items = organizer.jobstore.fetch_ready(limit=limit)
        return [{"path": fp, "name": Path(fp).name} for _, fp, _ in items]

    @app.get("/api/folder")
    def folder(path: str):
        folder = Path(path)
        proposal = organizer.jobstore.get_result(folder)
        if not proposal:
            raise HTTPException(404, "No completed proposal for path")
        metadata = organizer.directory_analyzer.extract_folder_metadata(folder)
        return {"metadata": metadata, "proposal": proposal}

    @app.post("/api/decision")
    def decision(payload: Dict[str, Any]):
        path = payload.get("path")
        action = payload.get("action")
        folder = Path(path)
        if action == "accept":
            proposal = payload.get("proposal")
            if not proposal:
                raise HTTPException(400, "proposal required for accept")
            organizer.state_manager.save_proposal_tracker(folder, proposal)
            # Mark job as accepted; mover worker will pick it up and perform file moves
            organizer.jobstore.update_latest_status_for_folder(folder, ["ready"], "accepted")
            organizer.progress_tracker.increment_processed()
            organizer.progress_tracker.increment_successful(proposal)
            return {"ok": True}
        elif action == "reconsider":
            fb = payload.get("feedback")
            user_classification = payload.get("user_classification")  # optional override: single_album|multi_disc_album|artist_collection
            # If the user is on a disc subfolder and indicates multi-disc, requeue the parent instead
            parent = folder.parent if user_classification == "multi_disc_album" else folder
            metadata = organizer.directory_analyzer.extract_folder_metadata(parent)
            if user_classification:
                metadata["user_classification"] = user_classification
            # Reset existing job back to queued to re-run with latest logic/feedback
            organizer.jobstore.requeue_for_reconsideration(parent, metadata, user_feedback=fb)
            return {"ok": True}
        elif action == "skip":
            organizer.jobstore.update_latest_status_for_folder(folder, ["ready"], "skipped")
            organizer.progress_tracker.increment_processed()
            organizer.progress_tracker.increment_skipped()
            return {"ok": True}
        else:
            raise HTTPException(400, "invalid action")

    # Shared SSE generator for status/events
    async def status_event_stream(request: Request):
        while True:
            if shutdown_event.is_set() or await request.is_disconnected():
                    break
            counts = organizer.jobstore.counts()
            stats = organizer.progress_tracker.get_stats()
            data = {
                "counts": counts,
                "processed": stats.get("total_processed", 0),
                "total": len(list(organizer.source_dir.iterdir())),
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)

    @app.get("/api/events")
    async def events(request: Request):
        return StreamingResponse(status_event_stream(request), media_type="text/event-stream")

    @app.get("/api/debug/jobs")
    def debug_jobs(limit: int = 100, statuses: Optional[str] = None):
        # statuses may be a comma-separated list
        status_list = [s.strip() for s in statuses.split(",")] if statuses else None
        return {
            "counts": organizer.jobstore.counts(),
            "recent": organizer.jobstore.recent_jobs(limit=limit, statuses=status_list),
        }

    # Development mode: redirect root to Vite dev server for HMR
    
    if os.getenv("WTS_DEV") == "1":
        # Simple reverse proxy to Vite dev server for HMR in dev.
        VITE_DEV_BASE = os.getenv("WTS_VITE_URL", "http://127.0.0.1:5173")
        project_root = Path(__file__).resolve().parent.parent
        dist_dir = project_root / "frontend" / "dist"

        async def proxy_request(request: Request, path: str):
            url = f"{VITE_DEV_BASE}{path}"
            # Stream request to Vite using httpx
            async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
                headers = {k.decode(): v.decode() for k, v in request.headers.raw if k.lower() not in {b"host"}}
                if request.method.upper() in {"GET", "HEAD"}:
                    r = await client.request(request.method, url, headers=headers)
                else:
                    body = await request.body()
                    r = await client.request(request.method, url, headers=headers, content=body)
            # Prepare streaming response with proxied status/headers/body
            response_headers = [(k.decode() if isinstance(k, bytes) else k, v) for k, v in r.headers.raw if k.lower() not in {b"transfer-encoding", b"content-encoding"}]
            return StreamingResponse(iter([r.content])), r.status_code, response_headers

        @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
        async def dev_proxy(full_path: str, request: Request):
            # Only proxy non-API routes; API paths are served by FastAPI
            if full_path.startswith("api/"):
                raise HTTPException(404)
            if full_path == "":
                path = "/"
            else:
                path = "/" + full_path
            try:
                proxied_body, status, headers = await proxy_request(request, path)
                return StreamingResponse(proxied_body, status_code=status, headers=dict(headers))
            except httpx.HTTPError:
                # Fallback: serve built asset if available
                if dist_dir.exists():
                    # Resolve file within dist
                    candidate = dist_dir / full_path
                    if candidate.is_file():
                        return FileResponse(str(candidate))
                    index_file = dist_dir / "index.html"
                    if index_file.is_file():
                        return FileResponse(str(index_file))
                # Else: return a clear 502 with guidance
                msg = (
                    f"Vite dev server unreachable at {VITE_DEV_BASE}.\n"
                    "Start it with 'npm run dev' in ./frontend, or build with 'npm run build' and restart without WTS_DEV.\n"
                    "You can also set WTS_VITE_URL to point at a reachable Vite dev URL."
                )
                return HTMLResponse(msg.replace("\n", "<br>"), status_code=502)
    else:
        # Mount built frontend (production) last so /api/* keeps priority
        try:
            project_root = Path(__file__).resolve().parent.parent
            dist_dir = project_root / "frontend" / "dist"
            if dist_dir.exists():
                app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
        except Exception:
            pass

    return app



def app_factory():
    """Build FastAPI app from environment settings. Used by uvicorn with --reload."""
    from pathlib import Path as _P
    from .inference import build_provider_from_env as _build_provider

    project_root = _P(__file__).resolve().parent.parent
    # Resolve dirs
    source_dir = os.getenv("WTS_SOURCE_DIR")
    target_dir = os.getenv("WTS_TARGET_DIR")
    if not source_dir:
        if (project_root / "tmp-src").exists():
            source_dir = str(project_root / "tmp-src")
        else:
            source_dir = str(_P.home() / "Music" / "Unsorted")
    if not target_dir:
        if (project_root / "tmp-dst").exists():
            target_dir = str(project_root / "tmp-dst")
        else:
            target_dir = str(_P.home() / "Music" / "Organized")

    # Inference from env (centralized)
    provider = _build_provider()

    # Build organizer
    src_path = _P(source_dir)
    dst_path = _P(target_dir)
    dst_path.mkdir(parents=True, exist_ok=True)
    src_path.mkdir(parents=True, exist_ok=True)

    organizer = MusicOrganizer(_P("model"), src_path, dst_path)
    organizer.inference = provider
    organizer.structure_classifier.inference = provider

    return create_app(organizer)
