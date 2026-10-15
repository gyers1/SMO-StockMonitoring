# SMO development

This is the independent active project. Do not reference the former hynix-ticker workspace or copy its runtime/cache files.

Preserve the compact Qt orb/ribbon, hover preview versus click pin, quotes/watchlist pages and Korean autocomplete. Use existing styles and surgical edits. State assumptions and verify observable behavior. Do not refactor unrelated code.

Entry: SMO.py. Runtime: Python 3.14 / PySide6. Create environment with uv and requirements-lock.txt. Run run-dev.bat; build with build.bat and Inno Setup 6. Keep the restricted build PATH: unrelated DLLs on developer PATH previously caused frozen Qt startup failure.

User data lives only in LOCALAPPDATA/SMO, never beside the source/executable. Never bundle ticker state, broker credentials or .env files. Keep broker API calls read-only. Do not fabricate prices, percentage changes, timestamps or unsupported broker support.

Before release: run qa/test_broker_quotes.py, applicable native QA, qa/check_package.py against the actual frozen executable, and install/uninstall smoke test. Never equate successful compilation with a working package. Record scope in qa/release-verification.md. No credential access for routine QA.

Rebuildable .venv/build/dist folders are not source and may be omitted from a clean handoff. Keep assets/fonts/OFL.txt and third-party license notices.

First-run guide: qt_onboarding.py, state in guide.ini beside user ticker state. Preserve app.setQuitOnLastWindowClosed(False); the tool-style main window must stay alive when guides/settings dialogs close. qa/check_onboarding.py covers ten action-driven steps and qa/check_package.py covers real startup, dismissal, and no-repeat.
