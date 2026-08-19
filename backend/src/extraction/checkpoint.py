"""
checkpoint.py

Tracks which emails have already been successfully extracted, so
batch_extract.py can be re-run daily and automatically skip completed
work rather than starting over or requiring manual tracking.
"""

import json
from pathlib import Path


class Checkpoint:
    """
    Wraps a simple JSON file storing the set of completed message_ids.
    """

    def __init__(self, checkpoint_path: Path):
        self.checkpoint_path = checkpoint_path
        self.completed_ids: set[str] = self._load()

    def _load(self) -> set[str]:
        """Loads existing progress from disk, or starts fresh if none exists."""
        if not self.checkpoint_path.exists():
            return set()

        with open(self.checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("completed_message_ids", []))

    def is_done(self, message_id: str) -> bool:
        """Checks whether this email was already successfully extracted."""
        return message_id in self.completed_ids

    def mark_done(self, message_id: str):
        """
        Marks one email as completed and immediately saves to disk.

        Saving after every single email (rather than batching saves) is
        deliberate: if the script crashes or is interrupted mid-run for
        any reason, we lose at most the one in-progress email, not the
        whole day's work.
        """
        self.completed_ids.add(message_id)
        self._save()

    def _save(self):
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(
                {"completed_message_ids": list(self.completed_ids)},
                f,
            )

    def progress_count(self) -> int:
        return len(self.completed_ids)