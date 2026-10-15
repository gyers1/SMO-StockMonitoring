# SMO 1.3.3 — 2026-10-15

- Confirmed user's shortcut target existed and installed old SMO remained responsive at second-monitor bottom. Old duplicate launch did not restore attention. New IPC relaunch recenters on cursor monitor; active guide anchor/geometry/step preserved.
- Failing-first launch regressions: anchor20,20 vs941,497; active-guide80,40 unexpectedly941,497. Both green after scoped fixes.
- Shared seven-size SMO ICO derives from actual glass surface/orb. Qt app, tray, EXE, installer and shortcut share it. Actual frozen PE icon group and seven icon resources verified.
- Toss official REST1.2.24 /rankings MARKET_TRADING_AMOUNT realtime KR/US count100 supplies decimal changeRate. Same row price/rate, five-second shared cache. Recent60s snapshot accepted. Older snapshot accepted only if /prices exact decimal price matches and valid full-precision timestamp is no newer than rankedAt; original snapshot time retained. Otherwise current price remains with unknown daily change. No candle inference.
- Live adapter check: Samsung210500/-9.26%, SK hynix1265000/-10.85%, KODEX20087025/-8.20%, AAPL344.78/+0.53%, NVDA218.65/-1.19%; IBM226.95 unknown (not ranked). These are observed provider values, not a guarantee of delay-free exchange ticks. No account/order endpoints used, no secrets logged.
- 103 tests passed. basedpyright on touched production:0errors/27 nonblocking warnings. A handled COM diagnostic appears during some QTest waits; suite completes and separate frozen tests pass.
- Fresh native12 screenshots+icon; independent final visual icon_guard_visual_final and functional launch_guard_final PASS. Active-guide issue caught and fixed before final capture/review.
- Final frozen real Shell Link launch, hidden-window relaunch to center, embedded icon, explicit Exit PASS. Actual installer/package/guide/hover/downward dashboard/tray recovery/production updater helper restart/uninstall PASS, previous uninstall registration preserved.
- Tested on this Windows host; not independent clean VM. No private profile included. Public update download verification follows publication.

---

# SMO 1.3.2 — 2026-10-15

- Concise menus/titles: 시세, 관심종목, 설정; settings: 업데이트, 사용 안내.
- First guide is claimed before display; interruption and legacy --guide no longer trigger repeat. Settings replay verified.
- Tray close/restore, offscreen recovery, duplicate launch restoration and explicit Exit verified.
- 70 regression tests passed. Basedpyright: 0 errors, 257 non-blocking warnings (Qt/unused-return conventions). Pytest reported a handled Windows COM diagnostic but completed; separate native/package tests completed without it.
- Fresh 12 native Qt captures in local qa/reliability; independent concise_visual and concise_function reviews both PASS.
- Final build log reports successful Inno compilation. Actual 1.3.2 installation, frozen startup/guide/hover/downward dashboard, tray restoration, explicit Exit, reinstall via production update helper/restart, and uninstall PASS. Existing uninstall registration preserved.
- Broker audit: qa/broker-audit-20261015.md. Toss candle-derived daily change removed; no fabricated fallback. Kiwoom wrapped exchange-not-found retry fixed; live five-symbol/two-round check passed. KIS fixture-only; Mirae unimplemented.
- User-reported spontaneous crash was not reproduced. Fixed exception and pending-request handling; added message-free local diagnostics. No claim that every crash is resolved.
- Native screenshots and private profiles are not published. No keys/accounts bundled. Build tested on this Windows host, not a separate clean VM.

---

# SMO 1.2.0 — 2026-10-15

- Added Korean Investment & Securities (KIS) real-account App Key / App Secret registration, official issue link, encrypted save/restore and quote routing.
- Domestic KRX and US NASDAQ/NYSE/AMEX read-only REST quote paths; 5-second refresh remains unchanged. US entitlement/delay is not assumed.
- 22 quote/transport regressions PASS, including exact request headers, token reuse, symbol mismatch, finite price, signed rate and credential non-leakage.
- Native KIS settings save/restore, DPAPI, password masking, required fields, provider switch and issue-link dispatch PASS. Connection probe response was simulated.
- Existing broker settings and seven-step onboarding regression PASS.
- Standalone basedpyright: 0 errors, 0 warnings. LSP daemon was unavailable; direct checker used.
- Independent functional-integrity and visual/CJK reviews PASS for both new settings states (qa/kis-settings.png, qa/kis-restored.png).
- PyInstaller build complete; Inno Setup compilation and temporary install/run/uninstall PASS. Frozen first-run guide, no-repeat, duplicate prevention, hover ribbon, clean exit and data isolation PASS.
- No live KIS key/production entitlement check performed. No personal credentials included in any artifact.

---

# SMO 1.1.0 — 2026-10-15

## User guide
- Seven real-control spotlight steps; first three teach hover preview versus click pin and collapse. Then broker setup, company-name search, group selection, watchlist/back.
- Only implemented functionality in user-facing text. 사용방법.md rewritten to match actual flow.
- App-only dimming, warm focus rim, softwhite Korean copy; surrounding desktop is not dimmed.
- Skip/Escape restores original view; Previous works; final CTA opens broker settings when unconfigured. guide.ini records completion; context menu replays guide.
- Native seven-step QA PASS: transitions, spotlight geometry, completion, settings handoff, unchanged groups, Previous/Escape restore. Fresh seven neutral captures guide-final-1.png through guide-final-7.png.
- Independent functional reviewer onboarding_function PASS; independent visual/CJK reviewer onboarding_visual PASS. Lifecycle followup reviewed as PASS.

## Actual distribution verification
- build.bat succeeded; exact final installer installed and uninstalled in temporary paths.
- Frozen app PASS: first-run guide opens, dismissing guide keeps app alive, hover expands, duplicate launch rejected, user state saves, explicit close exits, restarted app skips completed guide.
- Found and reproduced Qt last-dialog auto-quit with tool-style main window. setQuitOnLastWindowClosed(False) fixes it; explicit island.closeEvent still quits. Failing-first packaged assertion now passes.
- 14 broker boundary tests PASS. Compilation and selected Ruff error checks PASS. Changed-source type check: 0 errors / 117 warnings (existing Qt dynamic/unused-return typing).
- No user credentials read or included. Personal state remains LOCALAPPDATA/SMO. QA uses isolated temporary state.
- Installer SHA256: 8371f5053c80fdca7fd201aee1d3029d6f2133a5908b863f99dea71992a0d3bd
- Unsigned installer, tested on this Windows host rather than a separate clean VM. Python is bundled.
- Build environment and intermediate outputs removed after verification to retain the small independent development handoff.


## 1.3.0 release preparation (2026-10-15)
35 pytest tests passed; vertical101point regression, downward anchor/footer boundary, ten-action native guide, independent functional/visual reviewers PASS. Actual onedir executable startup/guide/hover/relaunch passed. Isolated installer and uninstaller passed; previous user uninstall registry exported/restored. Real PowerShell installer helper installed and restarted app successfully after removing incompatible DETACHED_PROCESS flag. Hover test now refreshes bounds after collapse settlement instead of reusing pre-transition bounds. Final rebuild includes update helper fix. Public anonymous download verification follows publication.

Final 1.3.0 artifact: 37,504,199 bytes, SHA-256 6440f7eb97477056f3f4091632a9dc4ec007eb709e8d19222d6bcd461ecfafba. 36 regression tests passed; final installer startup/downward-dashboard/install/uninstall and production helper install/restart smoke passed. Published GitHub release413438490 v1.3.0; anonymous check_release and download_release retrieved identical public bytes and verified hash. Full older-version update UI initiation is not exercised because prior1.2 has no updater; same-version reinstall/restart helper was exercised.
