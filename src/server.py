from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from .organizer import MusicOrganizer


def create_app(organizer: MusicOrganizer) -> FastAPI:
    app = FastAPI(title="What's That Sound API")

    @app.get("/")
    async def index():
        return HTMLResponse(
            content=
            """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>What's That Sound</title>
    <style>
      body { font-family: sans-serif; margin: 0; padding: 0; }
      header { padding: 8px 12px; background: #101820; color: #fff; }
      .grid { display: grid; grid-template-columns: 2fr 3fr 2fr; gap: 10px; padding: 10px; }
      .panel { border: 1px solid #ddd; padding: 10px; border-radius: 4px; }
      .title { font-weight: 700; margin-bottom: 6px; }
      button { padding: 6px 10px; margin-right: 6px; }
      pre { white-space: pre-wrap; }
    </style>
  </head>
  <body>
    <header>
      <div id="paths">Loading...</div>
    </header>
    <div class="grid">
      <div class="panel">
        <div class="title">Background</div>
        <div id="bg">-</div>
      </div>
      <div class="panel">
        <div class="title">Current Decision</div>
        <div id="current">Waiting for ready proposals...</div>
        <div id="actions" style="margin-top:8px;"></div>
      </div>
      <div class="panel">
        <div class="title">Ready</div>
        <ul id="ready"></ul>
      </div>
    </div>
    <script>
      async function fetchJSON(url, opts) { const r = await fetch(url, opts||{}); if (!r.ok) throw new Error(await r.text()); return await r.json(); }
      async function refreshStatus(){
        const s = await fetchJSON('/api/status');
        document.getElementById('paths').textContent = `Source: ${s.source_dir}  |  Target: ${s.target_dir}`;
        document.getElementById('bg').textContent = `Queue: ${s.counts.queued} | Running: ${s.counts.in_progress} | Ready: ${s.counts.completed} | Failed: ${s.counts.failed} | Processed: ${s.processed}/${s.total}`;
        const ul = document.getElementById('ready'); ul.innerHTML = '';
        s.ready.slice(0,10).forEach(item => { const li=document.createElement('li'); li.textContent=item.name; li.onclick=()=>loadDecision(item.path); ul.appendChild(li); });
        if (s.ready.length===0) { const li=document.createElement('li'); li.textContent='No ready items yet'; ul.appendChild(li); }
      }
      async function loadDecision(path){
        const d = await fetchJSON('/api/folder?path='+encodeURIComponent(path));
        const el = document.getElementById('current');
        el.innerHTML = `<div><b>${d.metadata.folder_name}</b> (${d.metadata.total_files} files)</div>` +
                       `<div>Artist: ${d.proposal.artist} | Album: ${d.proposal.album} | Year: ${d.proposal.year} | Type: ${d.proposal.release_type}</div>` +
                       `<pre>${(d.proposal.reasoning||'').slice(0,300)}</pre>`;
        const actions=document.getElementById('actions');
        actions.innerHTML='';
        const btnA=document.createElement('button'); btnA.textContent='Accept'; btnA.onclick=()=> decide(path,'accept',d.proposal);
        const btnR=document.createElement('button'); btnR.textContent='Reconsider'; btnR.onclick=()=> { const fb=prompt('Feedback?'); if(fb!==null) decide(path,'reconsider',null,fb); };
        const btnS=document.createElement('button'); btnS.textContent='Skip'; btnS.onclick=()=> decide(path,'skip');
        actions.appendChild(btnA); actions.appendChild(btnR); actions.appendChild(btnS);
      }
      async function decide(path, action, proposal, feedback){
        await fetchJSON('/api/decision',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ path, action, proposal, feedback })});
        document.getElementById('current').textContent='Processed.'; document.getElementById('actions').innerHTML='';
        refreshStatus();
      }
      function connectSSE(){
        const es = new EventSource('/api/events');
        es.onmessage = (e)=>{ try{ const s=JSON.parse(e.data); document.getElementById('bg').textContent = `Queue: ${s.counts.queued} | Running: ${s.counts.in_progress} | Ready: ${s.counts.completed} | Failed: ${s.counts.failed} | Processed: ${s.processed}/${s.total}`; }catch{} };
        es.onerror = ()=>{ es.close(); setTimeout(connectSSE,2000); };
      }
      refreshStatus(); connectSSE();
    </script>
  </body>
 </html>
            """,
            media_type="text/html",
        )

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


