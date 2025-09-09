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
    # Staged (unapplied) path changes
    staged_source: Optional[Path] = None
    staged_target: Optional[Path] = None

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
      .paths { display:flex; gap:12px; align-items:center; }
      .muted { color: #9bb; font-size: 12px; }
      #picker { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: none; align-items: center; justify-content: center; }
      #picker .dialog { background: #fff; color: #000; width: 640px; max-height: 70vh; overflow: auto; border-radius: 6px; padding: 10px; }
      #picker ul { list-style: none; padding-left: 0; }
      #picker li { padding: 4px 0; cursor: pointer; }
      #picker li:hover { background: #f2f6ff; }
    </style>
  </head>
  <body>
    <header>
      <div id="paths">
        <div class="paths"><b>Source:</b> <span id="curSource">-</span> <button onclick="openPicker('source')">Change</button></div>
        <div class="paths"><b>Target:</b> <span id="curTarget">-</span> <button onclick="openPicker('target')">Change</button></div>
        <div id="staged" class="muted"></div>
        <div id="applyBtns" style="margin-top:6px; display:none;">
          <button onclick="applyPaths('confirm')">Confirm</button>
          <button onclick="applyPaths('cancel')">Cancel</button>
        </div>
      </div>
    </header>
    <div id="picker">
      <div class="dialog">
        <div style="display:flex; align-items:center; gap:8px;">
          <div style="font-weight:700;">Select directory</div>
          <div style="flex:1"></div>
          <button onclick="closePicker()">Close</button>
        </div>
        <div style="margin-top:6px;">
          <div>Current: <span id="pickPath">/</span></div>
          <div style="margin-top:4px;">
            <button onclick="goUp()">Up</button>
            <button onclick="chooseCurrent()">Select this</button>
          </div>
          <ul id="pickList" style="margin-top:6px;"></ul>
        </div>
      </div>
    </div>
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
      let currentSource = ''; let currentTarget = ''; let stagedSource = ''; let stagedTarget = '';
      async function refreshPaths(){
        const p = await fetchJSON('/api/paths');
        currentSource = p.current.source_dir || '';
        currentTarget = p.current.target_dir || '';
        stagedSource = p.staged.source_dir || '';
        stagedTarget = p.staged.target_dir || '';
        document.getElementById('curSource').textContent = currentSource;
        document.getElementById('curTarget').textContent = currentTarget;
        const staged = [];
        if (stagedSource) staged.push(`Staged source: ${stagedSource}`);
        if (stagedTarget) staged.push(`Staged target: ${stagedTarget}`);
        document.getElementById('staged').textContent = staged.join('  |  ');
        document.getElementById('applyBtns').style.display = (stagedSource || stagedTarget) ? 'block' : 'none';
      }
      async function refreshStatus(){
        const s = await fetchJSON('/api/status');
        // Paths are shown via refreshPaths
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
      // Directory picker logic
      let pickWhich = null; let pickCurrent = '/';
      function openPicker(which){
        pickWhich = which;
        const desired = which==='source' ? (stagedSource || currentSource) : (stagedTarget || currentTarget);
        pickCurrent = desired || '/';
        document.getElementById('picker').style.display='flex';
        listDir();
      }
      function closePicker(){ document.getElementById('picker').style.display='none'; pickWhich=null; }
      async function listDir(){ document.getElementById('pickPath').textContent = pickCurrent; const d = await fetchJSON('/api/list?path='+encodeURIComponent(pickCurrent)); const ul=document.getElementById('pickList'); ul.innerHTML=''; if (d.parent){ const li=document.createElement('li'); li.textContent='..'; li.onclick=()=>{ pickCurrent=d.parent; listDir(); }; ul.appendChild(li);} d.entries.forEach(e=>{ const li=document.createElement('li'); li.textContent=e.name+'/'; li.onclick=()=>{ pickCurrent=e.path; listDir(); }; ul.appendChild(li); }); }
      function goUp(){ const p = document.getElementById('pickPath').textContent; const idx = p.lastIndexOf('/'); if (idx>0){ pickCurrent = p.slice(0,idx); listDir(); } }
      async function chooseCurrent(){ if (!pickWhich) return; const body = {}; if (pickWhich==='source') body.source_dir = pickCurrent; else body.target_dir = pickCurrent; await fetchJSON('/api/paths', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)}); await refreshPaths(); closePicker(); }
      async function applyPaths(action){ await fetchJSON('/api/paths', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ action })}); await refreshPaths(); await refreshStatus(); }
      refreshPaths(); refreshStatus(); connectSSE();
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


