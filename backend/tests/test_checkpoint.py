"""Tests for extraction checkpoint module."""
import json
import pytest
from pathlib import Path
from src.extraction.checkpoint import Checkpoint


class TestCheckpoint:
    def test_save_and_load(self, tmp_path):
        """Checkpoint round-trips correctly."""
        checkpoint_file = tmp_path / "test_checkpoint.json"
        
        # Save some IDs using the Checkpoint class
        ckpt = Checkpoint(checkpoint_file)
        for msg_id in {"<msg1@enron.com>", "<msg2@enron.com>", "<msg3@enron.com>"}:
            ckpt.mark_done(msg_id)
        
        # Load them back via a new instance
        loaded_ckpt = Checkpoint(checkpoint_file)
        assert loaded_ckpt.completed_ids == {"<msg1@enron.com>", "<msg2@enron.com>", "<msg3@enron.com>"}
    
    def test_load_nonexistent_returns_empty(self, tmp_path):
        """Loading a missing checkpoint returns an empty set."""
        checkpoint_file = tmp_path / "nonexistent.json"
        ckpt = Checkpoint(checkpoint_file)
        assert ckpt.completed_ids == set()
    
    def test_incremental_save(self, tmp_path):
        """Adding IDs and re-saving preserves all."""
        checkpoint_file = tmp_path / "test_checkpoint.json"
        
        ckpt = Checkpoint(checkpoint_file)
        ckpt.mark_done("<msg1@enron.com>")
        
        # Add more using a new reference to simulate re-opening
        ckpt_reload = Checkpoint(checkpoint_file)
        ckpt_reload.mark_done("<msg2@enron.com>")
        
        final_ckpt = Checkpoint(checkpoint_file)
        assert final_ckpt.progress_count() == 2
        assert final_ckpt.is_done("<msg1@enron.com>")
        assert final_ckpt.is_done("<msg2@enron.com>")
    
    def test_lookup_is_efficient(self, tmp_path):
        """Checkpoint uses set for O(1) lookup."""
        checkpoint_file = tmp_path / "test_checkpoint.json"
        
        ckpt = Checkpoint(checkpoint_file)
        for i in range(1000):
            ckpt.completed_ids.add(f"<msg{i}@enron.com>")
        ckpt._save()
        
        loaded_ckpt = Checkpoint(checkpoint_file)
        assert isinstance(loaded_ckpt.completed_ids, set)
        assert loaded_ckpt.is_done("<msg500@enron.com>")