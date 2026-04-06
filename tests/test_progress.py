from unittest.mock import MagicMock


class TestProgressRenderer:
    def test_init_without_channel(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        assert renderer._card is None

    def test_init_with_channel_creates_card(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel, enabled=True)
        assert renderer._card is mock_card

    def test_init_disabled_skips_card(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        renderer = ProgressRenderer(channel=mock_channel, enabled=False)
        assert renderer._card is None
        mock_channel.send_streaming_start.assert_not_called()

    def test_add_step_appends_to_list(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        renderer.add_step("Loading data")
        assert len(renderer._steps) == 1
        assert "Loading data..." in renderer._steps[0]

    def test_complete_step_marks_done(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        renderer.add_step("Loading data")
        renderer.complete_step("Loading data")
        assert "✅" in renderer._steps[0]
        assert "Loading data" in renderer._steps[0]

    def test_add_step_updates_card(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel)
        renderer.add_step("Step 1")
        mock_card.update_text.assert_called()

    def test_finish_calls_complete(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel)
        renderer.finish("Done", "Final content", "green")
        mock_card.complete.assert_called_once_with("Done", "Final content", "green")

    def test_finish_with_steps_includes_progress(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel)
        renderer.add_step("Step 1")
        renderer.complete_step("Step 1")
        renderer.finish("Done", "Final", "green")
        call_args = mock_card.complete.call_args[0]
        assert "Step 1" in call_args[1]
        assert "Final" in call_args[1]

    def test_warn_calls_complete_yellow(self):
        from x_agent_kit.progress import ProgressRenderer
        mock_channel = MagicMock()
        mock_card = MagicMock()
        mock_channel.send_streaming_start.return_value = mock_card
        renderer = ProgressRenderer(channel=mock_channel)
        renderer.warn("Warning title")
        mock_card.complete.assert_called_once()
        assert mock_card.complete.call_args[0][2] == "yellow"

    def test_update_text_with_no_card_is_noop(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        renderer.update_text("something")

    def test_finish_with_no_card_is_noop(self):
        from x_agent_kit.progress import ProgressRenderer
        renderer = ProgressRenderer(channel=None)
        renderer.finish("Done", "content")
