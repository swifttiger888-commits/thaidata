# ThaiData Phase 4 audit register — quantitative & consequential claims

Audit date: 2026-10-24. Auditor: Hermes (deepseek-v4-pro). Method: claim extracted from
published HTML, checked against FSA dataset in git, gov.uk, and the page's own arithmetic.

## Wage / tax claims

| Claim | URL | Verdict | Action |
|---|---|---|---|
| "From April 2026, NLW rises to £12.21/hour" (x2) | /glossary | WRONG — £12.21 was Apr 2025; Apr 2026 = £12.71 | Fixed both spots, incl. ~£14.50/hr total-cost figure |
| "April 2026 — 3 weeks away" / "before 1 April" | /nlw-report | STALE — April 2026 is past | Reframed to "rates now in force" |
| "£12.71 up from £11.44" (skipping £12.21) | /state-of-uk-thai-food-2026 (x2) | WRONG framing | Fixed: now cites £12.21 (Apr 2025) and £11.44 (2024) |
| NLW 12.71/10.85/8.00 with 4.1%/8.5%/6.0% deltas | /nlw-report, /index, /thai-restaurant-costs-uk | CORRECT, dated | No change |
| "£6,240/yr for 6 FT staff" | /nlw-report, /thai-restaurant-costs-uk | CORRECT (6×40×52×£0.50) | No change |
| Resilience dashboard "current" = £11.44/13.8% NI/£5k allowance | /tools/RESILIENCE_DASHBOARD | STALE (2024 baseline) | Fixed to Apr-2025 baseline (12.21/15%/£5k/£10.5k) |
| Staffing calc omits £10,500 Employment Allowance | /tools/thai-restaurant-staffing-calculator | Material omission | Output now states the allowance isn't deducted; NI rate dated |

## Delivery / commission claims

| Claim | URL | Verdict | Action |
|---|---|---|---|
| Green Curry example: "VAT (20%): £2.79" on £13.95 | /thai-restaurant-delivery-commissions-uk | WRONG — correct 1/6 = £2.33; profit recomputed £0.21→£0.67 | Fixed |
| "over 60% of customers find new restaurants through apps" | same | UNCITED | Removed; reworded without the stat |
| Pad Thai £14.50 comparison table (VAT 1/6, 14%/30% commissions) | same | CORRECT — re-verified all cells | No change |
| Commission rates 25–30%+marketing / 14% JE, dated June 2026 | same | Dated, framed as typical | No change |
| delivery-profit-calculator VAT/commission model | /tools | WRONG (VAT added on top; commission on net) | Rewritten: commission on VAT-incl. price, VAT 1/6; editable rates; DOM-verified |

## Restaurant economics / benchmarks

| Claim | URL | Verdict | Action |
|---|---|---|---|
| "Estimator based on real UK hospitality transaction data" | /tools/thai-restaurant-valuation | UNSUBSTANTIATED | Now "illustrative model… not based on transaction data" |
| Freehold = turnover ×0.5–1.0 property add | same | ARBITRARY | Removed; business-only range + surveyor note |
| Break-even used VAT-incl. price as revenue | /tools/thai-restaurant-break-even-calculator | WRONG (covers 79 vs true 95) | Fixed: price/1.2; DOM-verified 95 covers |
| "Real 2026 numbers" for 40-cover P&L | /thai-restaurant-costs-uk | OVERCLAIM for a model | Now "worked example… planning estimates" |
| Net-profit range 10–27% | /thai-restaurant-revenue-benchmarks-uk | Optimistic; owner-operated caveat missing | Added caveat + "planning ranges, not measurements" |
| Wholesale prices/surcharges (rice £13.99/£18.99, 3.2% NLW surcharge, NI 15%, oil £27.50–29.50) | /tools/WHOLESALE_BENCHMARKER | UNCITED | Qualified as ThaiData samples/estimates; NI surcharge flagged unverified |
| "Industry benchmark 4.2% net margin (UKHospitality 2024)" | /tools/PROFIT_MARGIN_DEFENDER | CITED, retained | No change |

## Immigration

| Claim | URL | Verdict | Action |
|---|---|---|---|
| RQF-6 requirement + £41,700/£33,400/£31,300 thresholds | /tools/VISA_ASSISTANT | Thresholds REAL (HC 997, 22 Jul 2025; gov.uk). But tool issued PASS verdicts for chef roles | Verdict engine REMOVED — chefs (SOC 5434) can't be newly sponsored; cost-only calculator + rules explainer + gov.uk links |
| Chef (5434) vs cook (5435) distinction | same | Missing | Now stated: cooks never eligible |

## Data-methodology claims

| Claim | URL | Verdict | Action |
|---|---|---|---|
| Dish prices: no sample size/date | /dish-prices | INCOMPLETE methodology | Added: mid-2026, 12 dishes, 5 cities, varying sample sizes, treat as ranges |
| "Neural crawler simulation / Neural trust score / AI utility / Waiting for neural analysis" | /tools/AI_AUDITOR, /tools/NAP_CHECKER, /tools/MENU_REVIEWER, /tools/MENU_SCHEMA_GENERATOR | MISLEADING — all client-side heuristics | Relabelled as heuristic/rule-based; no false AI claims remain |

## Flagged, not fixed (out of scope / needs owner decision)

- chains/*.html editorial claims (e.g. Chaophraya "£36m turnover at its peak", 2022 refurb investment) — specific and dated but uncited; chain pages carry no source block. Recommend a "sources" line per chain page.
- BENCHMARKS.html — subagent reported fully cited (Q1 2026 report); spot-checked, not re-verified figure-by-figure.
- VISA_ASSISTANT "IHS £3,105 for 3 years", "CoS £239", "licence £536–£1,476" — match real gov.uk fee schedules; kept.
