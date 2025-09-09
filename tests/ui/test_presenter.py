from pathlib import Path
from unittest.mock import Mock

from src.organizer import DecisionPresenter


def test_presenter_updates_dashboard(monkeypatch, tmp_path):
    # Minimal organizer double
    organizer = Mock()
    organizer.source_dir = tmp_path / "src"
    organizer.target_dir = tmp_path / "dst"
    organizer.jobstore.counts.return_value = {
        "queued": 1,
        "in_progress": 2,
        "completed": 1,
        "failed": 0,
    }
    organizer.jobstore.fetch_completed.return_value = []
    organizer.progress_tracker.get_stats.return_value = {"total_processed": 0}
    organizer._prefetch_proposals = Mock()
    organizer.ui.render_dashboard = Mock()

    folders = [tmp_path / "album1"]
    presenter = DecisionPresenter(organizer, folders)

    # Run one dashboard update
    presenter._update_dashboard()

    organizer.ui.render_dashboard.assert_called_once()


