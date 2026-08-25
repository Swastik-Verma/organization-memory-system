"""
Unit tests for the Permission Layer.

Run with:
    cd ~/Layer_10_Project2/backend
    python -m pytest tests/test_permissions.py -v
"""

import pytest
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.graph.permissions import (
    PermissionManager, UserContext,
    PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED,
    ACCESS_LEVEL_NAMES,
)


class TestUserContext:
    def test_default_clearance_is_public(self):
        user = UserContext(user_id="test")
        assert user.clearance_level == PUBLIC

    def test_can_access_own_level(self):
        user = UserContext(user_id="test", clearance_level=INTERNAL)
        assert user.can_access(INTERNAL) is True

    def test_can_access_lower_level(self):
        user = UserContext(user_id="test", clearance_level=CONFIDENTIAL)
        assert user.can_access(PUBLIC) is True
        assert user.can_access(INTERNAL) is True

    def test_cannot_access_higher_level(self):
        user = UserContext(user_id="test", clearance_level=INTERNAL)
        assert user.can_access(CONFIDENTIAL) is False
        assert user.can_access(RESTRICTED) is False

    def test_restricted_user_sees_everything(self):
        user = UserContext(user_id="admin", clearance_level=RESTRICTED)
        for level in [PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED]:
            assert user.can_access(level) is True

    def test_public_user_sees_only_public(self):
        user = UserContext(user_id="guest", clearance_level=PUBLIC)
        assert user.can_access(PUBLIC) is True
        assert user.can_access(INTERNAL) is False


class TestAccessLevelNames:
    def test_all_levels_named(self):
        assert ACCESS_LEVEL_NAMES[1] == "PUBLIC"
        assert ACCESS_LEVEL_NAMES[4] == "RESTRICTED"

    def test_levels_are_ordered(self):
        assert PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED