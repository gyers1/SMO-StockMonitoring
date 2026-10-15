# Mini ticker — glass ribbon

## Contract
Preserve full-market search, live quote cache and saved groups. Default expanded view
is a slim horizontal stock ribbon. Only the separate star opens group dashboard.
Hover previews ribbon; click pins; exit preview collapses; collapse control returns orb.

## Visual tokens
Black Iris #080813 base; soft white #ECEEF2 typography; neutral #B0B3BC metadata.
Frozen #A0BDDB reserved for glass rims, reflections and #192334/#293D53 grouped surfaces.
Warm #E6A16A only for active star/pin. No neon, flashing or decorative pulsing.
Bundled Pretendard Regular/SemiBold. Thin antialiased QPainter paths and per-pixel alpha;
text stays opaque while material opacity changes (preview70%, pinned90%).
Glass has subtle vertical tint gradient, bright top rim, inner rim and soft layered shadow.
Native OS blur is optional; don't fake moving desktop captures or claim unsupported blur.

## Layout
Orb36px; ribbon460x42px. Stock clip sits left; star and collapse controls fixed right.
Dashboard460x540px with 14px padding. Rounded body radius21px ribbon,24px dashboard.
Dashboard uses restrained grouped surfaces; full company names available via tooltip.

## Motion
120fps target: monotonic deadlines at 1/120s with Qt PreciseTimer; elapsed-time spring
integration, bounded dt, no network/layout work in paint or animation callbacks.
Morph spring stiffness280 damping29 (near critical, small gentle overshoot); don't animate
native OS window size each frame. Resize transparent host once, animate painted body,
then trim host at rest. Content fades only after body reaches readable size.
References: beui.dev feedback-widget morph (slight opening overshoot, calmer exit) and
Apple capsule/control hierarchy; actual geometry/motion follows this native desktop contract.
Ribbon: 3.6s readable dwell + .8s horizontal slide; both outgoing/incoming texts clipped
inside ribbon; sequence follows selected group's saved order and loops. No slide for one item.
Change group resets order. Pause hidden/dashboard; reduced-motion uses static transitions.
Hover delay200ms; leave grace500ms; prevent immediate re-open after explicit collapse.

## Validation
Capture orb/ribbon/dashboard. Exercise real pointer hover/pin/star/back/collapse,
check one/zero/many ticker entries, group switch, async quote errors, full search and state.
120 is scheduling target, not a guaranteed monitor refresh rate; record observed timings.

## Two dashboard pages
Ribbon controls left-to-right: magnifier (quotes), star (watchlist), collapse.
Quotes page has compact floating autocomplete max5 rows, about32px per row, opaque
raised dark surface separated from persistent watchlist. It never takes layout height.
Watchlist page has no search entry or suggestions and devotes body to group holdings.
Both pages have visible '한 줄로' back button and collapse to orb on outside click.
App-owned group menus/dialogs are excluded from outside-click collapse.
Successful additions use a short flying stock chip into the watchlist and inline saved
confirmation. Duplicate additions and save errors show distinct inline text. Motion
runs at120fps target and is cancelled on page change/collapse; no modal success popup.

## Broker settings
Keep the existing compact native Qt style. A small settings control in each dashboard
header and a right-click menu entry open a 420px modal using shared qt_styles tokens.
Choose one broker; masked key and secret, explicit reveal checkbox, official issuance
link, asynchronous connection check, save/apply, delete and cancel are separate actions.
Credentials are DPAPI protected per Windows user, outside the shared app folder.
Toss/Kiwoom are active; Mirae shows its verified AnyLink availability restriction and
official information link rather than accepting nonfunctional credentials.
No credential means no price. Provider changes clear cached quotes; no public fallback.
Holdings/account view omitted per user preference for a lightweight quotes app.

## First-run guide (SMO 1.1)
Reference image is an interaction example only, not a pixel/style target. Preserve SMO tokens.
Seven coach steps: orb hover/click, pinned ribbon/collapse, collapsed orb, API settings,
company-name search, group selection/manage, watchlist/back. First three explain the core
preview-versus-pin distinction before setup. Use real UI behind an application-modal guide.
Dim only app surface outside the current focus; leave the surrounding desktop unchanged.
Focus rim warm #E6A16A, 2px. Coach card #10131E, Frozen rim #465267, radius20,
width360, padding20, spacing12, softwhite title16/body12, neutral metadata11.
Guide follows actual settled widget geometry; no screenshots or synthetic prices. Position
card beside app or above/below within available monitor bounds. Skip/Escape, previous and
next are keyboard accessible. One-time marker guide.ini per user; context-menu replay.
Suspend automatic pointer collapse during guide; restore original view on skip. Finish
opens broker setup for unconfigured users, or pinned ribbon for configured users. Do not
change groups, query, credentials, or saved window position during the tour.

## SMO guided interaction revision
This revision supersedes conflicting first-run and broker paragraphs above.
Native Qt remains the renderer; no React/Lighthouse or web framework is introduced.
Audience: nontechnical desktop users glancing at stocks while working. Preserve compact
ribbon and visible escape/skip; never require API credentials to learn the controls.
Coach is nonmodal with a native input-region hole over the live target. Progress follows
actual pin/collapse/hover/search selection/navigation; no Next action substitutes for it.
Coach #192334, border #465267, text #F5F6F8, body14px weight600, title17px weight700,
width380 padding20. Action hint and ring #E6A16A; ring alpha cycles 100..245 over1.8s,
never flashes. Card stays outside focused target. Reduced-motion keeps ring steady.
First launch lands the36px orb in available-screen center. Startup: enlarged68px orb
appears above center, drops56px, makes one small rebound, settles36px in1.25s. Saved
positions are preserved on subsequent launches after the brief centered introduction.
Keep transparent host fixed during startup; only painted geometry moves. Honor Windows
client-area animation preference with a static introduction. No continuous decoration.
Currency is rendered as ₩/$/¥/€/£; country uses bundled small flag SVGs with text tooltip,
not platform-dependent emoji. Keep exchange name beside flag to disambiguate listings.
Save connection: immutable input snapshot -> background real quote probe -> encrypted save
only on success. Visible warm-orange success remains in dialog; failures preserve old key.
Mirae label has no disabled suffix; details explicitly describe integration availability.
Update settings: current version/check/download states, warm-orange horizontal progress
using bytes actually received; never fake progress. SHA256 verification required before
launching installer. No install during this preview. Startup check is quiet if no release.
GitHub source is a fixed reviewed public owner/repository; no distributed GitHub token.

## Reliability and recovery (1.3.2)
System tray uses the existing SMO three-bar orb artwork and shared QMenu colors.
Left click restores a visible orb on the current monitor if necessary; menu offers
show, quotes, watchlist, settings and explicit exit. Closing the floating window
hides to tray, preserving quote workers; explicit exit shuts down. No second taskbar
button when the tray is available. Relaunching an already-running app restores it.
Guide automatically appears only once per user profile: persist shown before display,
also honor existing completed marker. Dismissal keeps it off on future launches.
Settings reuse existing button typography/spacing for '사용 안내 다시 보기'; close
settings before opening the nonmodal tutorial. No new colors or animation patterns.

Quote direction: orange rise, Frozen fall, softwhite flat or unknown. Unknown displays 등락 — in ribbon and 등락률 확인 불가 in dashboard; tooltip explains provider limitations. Never color an unknown or flat quote as a fall.
