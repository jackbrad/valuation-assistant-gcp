# 08 — Web app (reviewer UI + API)

FastAPI, Jinja2 templates, vanilla JS. One Cloud Run service `valuation-app`. Clean, sober UI: this is shown on a screen share, so large type (≥16px), high contrast, no clutter. Fictional branding only: "Valuation Review Workbench".

## Demo users (switcher in the header, labeled "Demo user")

| User | Role | Has stake |
|---|---|---|
| `alex.reviewer` | appraisal_reviewer | no |
| `sam.reviewer` | appraisal_reviewer | no |
| `pat.steward` | data_steward | no |
| `jordan.lo` | loan_officer | yes, for 14 Larkspur Ln |
| `casey.appraiser` | appraiser (can sign off, G3) | no |

`# DEMO-SHORTCUT:` identity comes from a signed cookie set by the switcher. Production: IAP + Google identity, roles from groups.

## Pages

1. **Ask** (`/`) — chat on the left; **Evidence panel** on the right, rendered from captured tool results:
   - Value card: range, point, confidence, gate result + reasons, "Sign off" (G3, appraiser only).
   - Facts table: field · value · source type · citation link · status badge (`held`, `corrected`) · "This is wrong".
   - Comp grid: address · sale date · distance · time factor · per-feature adjustments · adjusted price · weight · Keep/Reject · "This is wrong".
   - Document snippets with citation links.
   - Citation link opens the PDF page image in a side viewer with the bbox highlighted.
2. **Review queue** (`/review`) — tabs by route; item detail shows the flag, current fact + citation, proposed value, evidence viewer, prior decisions, Approve / Reject with notes. Approve is disabled with a tooltip explaining why (same user, stake, missing evidence).
3. **What changed** (`/changes/{correction_id}`) — cascade results: old vs. new range per affected valuation, highlighted cause.
4. **Model health** (`/health`) — breaker state per submarket, latest eval runs, champion versions, adjustment grid per submarket.

## API

| Method & path | Purpose |
|---|---|
| `POST /api/chat` | `{session_id, message}` → `{answer_markdown, evidence}` (evidence = captured tool outputs) |
| `GET /api/properties/{id}/facts` | facts with citations |
| `GET /api/valuations/{id}` | valuation + comps |
| `POST /api/valuations` | run a valuation directly (used by UI buttons and tests) |
| `POST /api/flags` | multipart flag + evidence |
| `GET /api/review` / `GET /api/review/{id}` | queue / item |
| `POST /api/review/{id}/decision` | approve/reject |
| `POST /api/comp-feedback` | keep/reject a comp |
| `POST /api/signoffs` | G3 sign-off |
| `GET /api/docs/{doc_id}/pages/{n}.png` | rendered page image (cached in GCS) |
| `POST /api/breaker/{submarket}/ack` | human acknowledgement |
| `POST /_pubsub/flags`, `POST /_pubsub/corrections` | push endpoints (verify OIDC token) |
| `GET /healthz` | liveness |

## Performance targets

Page load < 1 s after warm. Chat answer < 10 s. Set Cloud Run `min-instances=1` for the demo window and `cpu-boost` on.
