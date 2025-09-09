from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .organizer import MusicOrganizer


def create_app(organizer: MusicOrganizer) -> FastAPI:
    app = FastAPI(title="What's That Sound API")
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

    # Frontend is served by Vite in development. In production, serve built assets if present.
    try:
        project_root = Path(__file__).resolve().parent.parent
        dist_dir = project_root / "frontend" / "dist"
        if dist_dir.exists():
            app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
    except Exception:
        # If anything goes wrong determining the dist path, skip mounting
        pass

    @app.get("/api/status")
    async def status():
        counts = organizer.jobstore.counts()
        ready = organizer.jobstore.fetch_completed(limit=20)
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
    async def get_paths():
        return {
            "current": {"source_dir": str(organizer.source_dir), "target_dir": str(organizer.target_dir)},
            "staged": {
                "source_dir": str(staged_source) if staged_source else "",
                "target_dir": str(staged_target) if staged_target else "",
            },
        }

    @app.post("/api/paths")
    async def post_paths(payload: Dict[str, Any]):
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
            # Re-run discovery and prefetch like at start
            try:
                folders = []
                try:
                    from .organizer import FolderDiscovery  # local import to avoid cycles
                    fd = FolderDiscovery(organizer.source_dir, organizer.state_manager)
                    folders = fd.discover() or []
                except Exception:
                    folders = []
                if folders:
                    try:
                        organizer._prefetch_proposals(folders)
                    except Exception:
                        pass
            finally:
                staged_source = None
                staged_target = None
            return {"ok": True}
        raise HTTPException(400, "invalid action")

    @app.get("/api/list")
    async def list_dirs(path: str):
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
    async def ready(limit: int = 20):
        items = organizer.jobstore.fetch_completed(limit=limit)
        return [{"path": fp, "name": Path(fp).name} for _, fp, _ in items]

    @app.get("/api/folder")
    async def folder(path: str):
        folder = Path(path)
        proposal = organizer.jobstore.get_result(folder)
        if not proposal:
            raise HTTPException(404, "No completed proposal for path")
        metadata = organizer.directory_analyzer.extract_folder_metadata(folder)
        return {"metadata": metadata, "proposal": proposal}

    @app.post("/api/decision")
    async def decision(payload: Dict[str, Any]):
        path = payload.get("path")
        action = payload.get("action")
        folder = Path(path)
        if action == "accept":
            proposal = payload.get("proposal")
            if not proposal:
                raise HTTPException(400, "proposal required for accept")
            organizer.state_manager.save_proposal_tracker(folder, proposal)
            organizer.file_organizer.organize_folder(folder, proposal)
            organizer.progress_tracker.increment_processed()
            organizer.progress_tracker.increment_successful(proposal)
            return {"ok": True}
        elif action == "reconsider":
            fb = payload.get("feedback")
            metadata = organizer.directory_analyzer.extract_folder_metadata(folder)
            organizer.jobstore.enqueue(folder, metadata, user_feedback=fb)
            return {"ok": True}
        elif action == "skip":
            organizer.progress_tracker.increment_processed()
            organizer.progress_tracker.increment_skipped()
            return {"ok": True}
        else:
            raise HTTPException(400, "invalid action")

    @app.get("/api/events")
    async def events(request: Request):
        async def gen():
            while True:
                if await request.is_disconnected():
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
        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


