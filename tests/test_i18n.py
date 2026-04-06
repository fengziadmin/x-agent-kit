import pytest


class TestI18nCore:
    def test_default_locale_is_zh_cn(self):
        from x_agent_kit.i18n import get_locale
        assert get_locale() == "zh_CN"

    def test_t_returns_chinese_by_default(self):
        from x_agent_kit.i18n import t
        result = t("agent.thinking")
        assert "分析" in result

    def test_t_with_interpolation(self):
        from x_agent_kit.i18n import t
        result = t("plan.pending_count", pending=3, total=5)
        assert "3" in result
        assert "5" in result

    def test_t_fallback_to_default(self):
        from x_agent_kit.i18n import t
        result = t("nonexistent.key", default="fallback_value")
        assert result == "fallback_value"

    def test_t_fallback_to_key_when_no_default(self):
        from x_agent_kit.i18n import t
        result = t("nonexistent.key")
        assert result == "nonexistent.key"

    def test_set_locale_switches_to_english(self):
        from x_agent_kit.i18n import t, set_locale
        set_locale("en")
        result = t("agent.thinking")
        assert "Thinking" in result
        set_locale("zh_CN")

    def test_get_locale_reflects_change(self):
        from x_agent_kit.i18n import get_locale, set_locale
        set_locale("en")
        assert get_locale() == "en"
        set_locale("zh_CN")
        assert get_locale() == "zh_CN"

    def test_load_extra_locale_merges_keys(self):
        import json
        import tempfile
        from pathlib import Path
        from x_agent_kit.i18n import t, set_locale, load_extra_locale
        set_locale("zh_CN")
        extra = {"custom.greeting": "你好世界"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(extra, f)
            f.flush()
            load_extra_locale(f.name)
        assert t("custom.greeting") == "你好世界"
        assert "分析" in t("agent.thinking")
        set_locale("zh_CN")

    def test_load_extra_locale_overrides_framework_keys(self):
        import json
        import tempfile
        from x_agent_kit.i18n import t, set_locale, load_extra_locale
        set_locale("zh_CN")
        extra = {"agent.thinking": "CUSTOM THINKING"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(extra, f)
            f.flush()
            load_extra_locale(f.name)
        assert t("agent.thinking") == "CUSTOM THINKING"
        set_locale("zh_CN")

    def test_set_locale_invalid_falls_back_to_zh_cn(self):
        from x_agent_kit.i18n import t, set_locale
        set_locale("fr_FR")
        assert "分析" in t("agent.thinking")
        set_locale("zh_CN")
