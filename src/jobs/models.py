from dataclasses import dataclass


@dataclass
class Job:
    job_id: int
    folder_path: str
    metadata_json: str
    user_feedback: str | None
    artist_hint: str | None
    status: str
    job_type: str


