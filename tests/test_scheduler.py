from unittest.mock import MagicMock, patch

class TestScheduler:
    def test_add_job(self):
        with patch("x_agent_kit.scheduler.BackgroundScheduler") as mock_cls:
            from x_agent_kit.scheduler import Scheduler
            mock_cls.return_value = MagicMock()
            sched = Scheduler()
            sched.add("0 */6 * * *", lambda: None)
            assert mock_cls.return_value.add_job.called

    def test_start(self):
        with patch("x_agent_kit.scheduler.BackgroundScheduler") as mock_cls:
            from x_agent_kit.scheduler import Scheduler
            mock_cls.return_value = MagicMock()
            sched = Scheduler()
            sched.start()
            assert mock_cls.return_value.start.called

    def test_stop(self):
        with patch("x_agent_kit.scheduler.BackgroundScheduler") as mock_cls:
            from x_agent_kit.scheduler import Scheduler
            mock_cls.return_value = MagicMock()
            sched = Scheduler()
            sched.stop()
            assert mock_cls.return_value.shutdown.called
