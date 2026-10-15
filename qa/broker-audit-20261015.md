# Broker accuracy audit — 2026-10-15

This audit supersedes the old Toss percentage statements in 1.3.1 evidence. No personal keys, tokens, account identifiers, raw authentication bodies, or private holdings are stored in these artifacts.

## Official contracts checked

- Toss canonical OpenAPI: https://openapi.tossinvest.com/openapi-docs/latest/openapi.json
- Discovery: https://developers.tossinvest.com/llms.txt
- Kiwoom canonical specification: https://raw.githubusercontent.com/Kiwoom-Securities/Kiwoom-REST-API/main/kiwoom/_data/kiwoom_api_spec.json
- KIS domestic current price: https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_price
- KIS US current price: https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/price

Toss /prices provides lastPrice, currency, symbol and timestamp, but no daily baseline/change. Daily candles can include a different trading-session close than the regular-session previous close. Live Samsung price 205500 yielded candle-derived -12.3667% while Kiwoom returned -11.42%; AAPL346 yielded +0.8864% versus Kiwoom+1.39%. This is sufficient to reject the prior assumption, not independent proof that every broker field reflects exchange ticks without delay. Rankings exposes basePrice/changeRate but only top100 rankings, no arbitrary symbol lookup or per-quote matching session identity. Therefore SMO no longer substitutes chart-derived percentage for official daily change. It keeps Toss price and explicitly marks percentage unavailable. Deleted orphan candle helper and its network allowlist entry; replacement tests forbid fabricated daily change rather than preserving invalid behavior.

Kiwoom flu_rt is signed percentage, cur_prc signed price whose magnitude is the monetary price. US API uses ND/NY/NA. Live IBM/ND returned wrapper return_code7 with canonical [1903:...] inside return_msg. The old code aborted before NYSE. The fix retries another exchange only for known 1901/1902/1903 errors, including exact code7 wrapper, and never emits raw return_msg. Generic7 still fails. IBM/NY now succeeds and exchange identity remains checked.

KIS domestic prdy_ctrt is retained; US rate magnitude follows sign1/2 positive,3 neutral,4/5 negative; unknown sign stays unavailable. Unsupported Mirae does not issue network requests. No credentials were available for KIS; these claims are official-contract/fixture verification, not live account verification.

## Runtime reliability fixes

BrokerError was a frozen/slotted exception dataclass: contextlib assigning __traceback__ raised a new TypeError. A generator-context regression reproduced this and now passes with a mutable exception dataclass. QuoteService had no finally cleanup on unexpected worker failure, stranding a pending symbol forever. Cleanup now always frees pending work and marks a generic error without exposing exception content; unexpected exception still propagates. Known failures preserve last confirmed quote and mark it as an error. Auth401 clears token for the next request.

## Live evidence

qa/broker-audit-live.json contains sanitized public quote values from read-only authentication and quote calls, at 2026-10-15 06:02 UTC. User had explicitly authorized these Toss/Kiwoom credentials. No account or trading endpoints were called.

- Kiwoom: Samsung, EcoPro BM, KODEX200, AAPL and IBM, two consecutive rounds: 10/10 quote loads succeeded, with signed daily percentage, currency and exchange.
- Toss: first five symbols succeeded; second domestic three succeeded, then AAPL/IBM returned HTTP401. A separate freshly authorized batch retry returned200 for both AAPL and IBM. Cause of intermittent401 was not established; do not report all repeated calls as successful or promise uninterrupted entitlement. Existing auth invalidation/retry behavior is covered by a regression.
- These calls verify authentication, parsing and refresh attempts. They are not an independent exchange-feed accuracy, latency, or all-instrument entitlement guarantee. Kiwoom/KIS endpoints do not provide execution timestamps; SMO preserves timestamp0 and separately records receipt time.

## Tests

Red before fixes: wrapped Kiwoom missing-exchange aborted, frozen exception changed into TypeError, unexpected worker failure retained pending. The initial candle timezone regression also showed wrong0% across Korean midnight; the entire unsafe chart inference was subsequently removed instead of fixing only timezone while retaining a wrong baseline.

Final: 46 passed across qa/test_broker_audit.py, qa/test_broker_quotes.py, qa/test_kis.py, qa/test_toss_change.py. basedpyright of broker_adapter.py, broker_types.py, broker_transport.py and quote_service.py: 0 errors. Added up/down/neutral/missing domestic coverage for Kiwoom/KIS, KIS US direction codes, exact wrapper errors, no invented Toss changes, reauthorization, stale quote retention and pending cleanup.
