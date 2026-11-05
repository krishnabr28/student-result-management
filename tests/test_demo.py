import importlib

import app.demo


def test_custom_demo_password_is_used_and_never_offered_as_one_click_login(monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "Random-Admin-Secret-42")
    demo = importlib.reload(app.demo)
    try:
        assert demo.DEMO_PASSWORDS["admin"] == "Random-Admin-Secret-42"
        assert [username for _, username, _ in demo.DEMO_ACCOUNTS] == ["faculty", "241203106130"]
    finally:
        monkeypatch.delenv("DEMO_ADMIN_PASSWORD")
        importlib.reload(app.demo)


def test_defaults_offer_all_three_demo_logins():
    assert [username for _, username, _ in app.demo.DEMO_ACCOUNTS] == ["admin", "faculty", "241203106130"]
