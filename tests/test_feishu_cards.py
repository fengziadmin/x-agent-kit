from __future__ import annotations


class TestBuildConfirmationCard:
    def test_returns_dict(self):
        from x_agent_kit.channels.feishu_cards import build_confirmation_card
        card = build_confirmation_card("req-1", "暂停广告", "详情")
        assert isinstance(card, dict)
        assert card["schema"] == "2.0"

    def test_has_approve_reject_buttons(self):
        from x_agent_kit.channels.feishu_cards import build_confirmation_card
        card = build_confirmation_card("req-1", "暂停", "详情")
        body = str(card)
        assert "approve" in body
        assert "reject" in body

    def test_has_orange_header(self):
        from x_agent_kit.channels.feishu_cards import build_confirmation_card
        card = build_confirmation_card("req-1", "暂停", "详情")
        assert card["header"]["template"] == "orange"

    def test_request_id_in_buttons(self):
        from x_agent_kit.channels.feishu_cards import build_confirmation_card
        card = build_confirmation_card("test-id-123", "操作", "详情")
        body = str(card)
        assert "test-id-123" in body


class TestBuildStatusCard:
    def test_complete_is_green(self):
        from x_agent_kit.channels.feishu_cards import build_status_card
        card = build_status_card("Done", "complete", "green", "All good")
        assert card["header"]["template"] == "green"

    def test_error_is_red(self):
        from x_agent_kit.channels.feishu_cards import build_status_card
        card = build_status_card("Failed", "error", "red")
        assert card["header"]["template"] == "red"

    def test_has_tag(self):
        from x_agent_kit.channels.feishu_cards import build_status_card
        card = build_status_card("Processing", "processing", "blue")
        tags = card["header"]["text_tag_list"]
        assert len(tags) > 0


class TestStreamingCard:
    def test_init(self):
        from unittest.mock import MagicMock
        from x_agent_kit.channels.feishu_cards import StreamingCard
        card = StreamingCard(MagicMock(), "oc_test")
        assert card._card_id is None
        assert card._sequence == 0
