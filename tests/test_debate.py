"""Tests for bl-debater core functionality."""

import pytest
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bl_debater.debate import DebateManager


@pytest.fixture
def temp_debates_dir():
    """Create a temporary directory for debates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manager(temp_debates_dir):
    """Create a DebateManager with temp directory."""
    return DebateManager(temp_debates_dir)


class TestDebateManager:
    """Tests for DebateManager."""

    def test_start_creates_debate_file(self, manager, temp_debates_dir):
        """Starting a debate creates the markdown file."""
        debate_file, instructions = manager.start(
            name="test_debate",
            prompt="Should we use REST or GraphQL?",
            role="architect",
            opponent_role="backend"
        )

        assert debate_file.exists()
        assert debate_file.name == "test_debate.md"
        assert "REST or GraphQL" in debate_file.read_text()

    def test_start_includes_waiting_marker(self, manager):
        """Starting a debate includes the starter's waiting marker."""
        debate_file, _ = manager.start(
            name="marker_test",
            prompt="Test prompt",
            role="architect",
            opponent_role="security"
        )

        content = debate_file.read_text()
        assert "[WAITING_ARCHITECT]" in content

    def test_start_duplicate_raises_error(self, manager):
        """Starting a debate with existing name raises error."""
        manager.start("duplicate", "Prompt", "architect", "backend")

        with pytest.raises(ValueError, match="already exists"):
            manager.start("duplicate", "Another prompt", "frontend", "qa")

    def test_join_existing_debate(self, manager):
        """Joining an existing debate returns file and instructions."""
        manager.start("join_test", "Test", "architect", "security")

        debate_file, instructions, is_your_turn = manager.join(
            name="join_test",
            role="security"
        )

        assert debate_file.exists()
        assert not is_your_turn  # architect goes first

    def test_join_as_starter_is_your_turn(self, manager):
        """Joining as the starter means it's your turn."""
        manager.start("turn_test", "Test", "architect", "security")

        _, _, is_your_turn = manager.join("turn_test", "architect")

        assert is_your_turn

    def test_join_nonexistent_raises_error(self, manager):
        """Joining nonexistent debate raises error."""
        with pytest.raises(ValueError, match="not found"):
            manager.join("nonexistent", "architect")

    def test_join_wrong_role_raises_error(self, manager):
        """Joining with wrong role raises error."""
        manager.start("role_test", "Test", "architect", "security")

        with pytest.raises(ValueError, match="not a participant"):
            manager.join("role_test", "frontend")

    def test_get_status(self, manager):
        """Getting status returns debate info."""
        manager.start("status_test", "Test prompt", "architect", "backend")

        status = manager.get_status("status_test")

        assert status["role1"] == "architect"
        assert status["role2"] == "backend"
        assert status["round"] == 1
        assert status["current_turn"] == "architect"
        assert not status["is_complete"]

    def test_list_debates(self, manager):
        """Listing debates returns all debates."""
        manager.start("debate1", "First", "architect", "security")
        manager.start("debate2", "Second", "frontend", "backend")

        debates = manager.list_debates()

        assert len(debates) == 2
        names = [d["name"] for d in debates]
        assert "debate1" in names
        assert "debate2" in names

    def test_debate_complete_detection(self, manager):
        """Debate completion is detected from marker."""
        debate_file, _ = manager.start("complete_test", "Test", "a", "b")

        # Manually add completion marker
        content = debate_file.read_text()
        content += "\n[DEBATE_COMPLETE]\n"
        debate_file.write_text(content)

        status = manager.get_status("complete_test")
        assert status["is_complete"]

    def test_wait_returns_immediately_when_marker_present(self, manager):
        """Wait returns immediately when marker is already present."""
        manager.start("wait_test", "Test", "architect", "security")

        # Should return immediately since [WAITING_ARCHITECT] is in file
        result = manager.wait_for_turn("wait_test", "architect", timeout=1)

        assert result == "YOUR_TURN"

    def test_wait_timeout_when_marker_absent(self, manager):
        """Wait times out when marker is not present."""
        manager.start("timeout_test", "Test", "architect", "security")

        # Security's marker is not present, should timeout
        with pytest.raises(TimeoutError):
            manager.wait_for_turn("timeout_test", "security", timeout=1, poll_interval=0.1)
