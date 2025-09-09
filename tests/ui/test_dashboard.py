from src.ui import InteractiveUI


def test_render_dashboard_smoke(tmp_path):
    ui = InteractiveUI()
    ui.start_live()
    try:
        ui.render_dashboard(
            source_dir=str(tmp_path / "src"),
            target_dir=str(tmp_path / "dst"),
            queued=3,
            running=2,
            ready=1,
            failed=0,
            processed=5,
            total=10,
            deciding_now="Album A",
            ready_examples=["Album B", "Album C"],
        )
    finally:
        ui.stop_live()


