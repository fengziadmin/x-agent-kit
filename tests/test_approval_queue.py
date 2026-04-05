from pathlib import Path


class TestApprovalQueue:
    def _make_queue(self, tmp_path):
        from x_agent_kit.approval_queue import ApprovalQueue
        db_path = str(tmp_path / "test.db")
        return ApprovalQueue(db_path=db_path)

    def test_add_and_get(self, tmp_path):
        q = self._make_queue(tmp_path)
        q.add("req-1", "Pause campaign", "Details here", "pause_campaign", {"id": "123"})
        item = q.get("req-1")
        assert item is not None
        assert item["action"] == "Pause campaign"
        assert item["tool_name"] == "pause_campaign"
        assert item["status"] == "pending"

    def test_get_nonexistent(self, tmp_path):
        q = self._make_queue(tmp_path)
        assert q.get("nonexistent") is None

    def test_resolve_approved(self, tmp_path):
        q = self._make_queue(tmp_path)
        q.add("req-2", "Change budget", "Details", "adjust_budget", {"amount": 100})
        q.resolve("req-2", "APPROVED")
        item = q.get("req-2")
        assert item["status"] == "APPROVED"

    def test_resolve_rejected(self, tmp_path):
        q = self._make_queue(tmp_path)
        q.add("req-3", "Delete", "Details", "delete_campaign", {})
        q.resolve("req-3", "REJECTED")
        item = q.get("req-3")
        assert item["status"] == "REJECTED"

    def test_pending_count(self, tmp_path):
        q = self._make_queue(tmp_path)
        assert q.pending_count() == 0
        q.add("a", "A", "D", "tool_a", {})
        q.add("b", "B", "D", "tool_b", {})
        assert q.pending_count() == 2
        q.resolve("a", "APPROVED")
        assert q.pending_count() == 1
