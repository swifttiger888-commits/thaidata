# Hybrid Triage — Chinese/Thai entries in live data (policy: authentic Thai only)

Date: 2026-10-15 · Status: FOR REVIEW — no removals executed yet
Method: name-scan of restaurants.json → per-venue web evidence (official site / Facebook / Just-Eat / TripAdvisor)

## REMOVE — 11 (Chinese-front or multi-brand; not authentic Thai)
| FSA ID | Name | City | Evidence |
|---|---|---|---|
| 628243 | Honeymoon Chinese And Thai | Barnstaple | FB + site: "Honeymoon Chinese… serves Chinese cuisine"; TA "Honeymoon Chinese Restaurant" |
| 312971 | Beijing Chinese & Thai Takeaway | Bristol | own site "Beijing Chinese takeaway"; Chinese-first branding |
| 157150 | De Bao Chinese & Thai Takeaway | Skegness | "De Bao Chinese Takeaway" branding; FB "Chinese/Thai" |
| 1817876 | Golden Fields Chinese & Thai | Manchester | Uber: "specialises in Chinese cuisine with a selection of Thai dishes"; site "GOLDEN FIELDS Chinese Takeaway" |
| 1690364 | Oriental Hub / Kings Of Thai | Farnborough | site "Chinese & Thai Takeaway"; Just-Eat "Wide selection of Chinese" |
| 1053137 | Chens Chinese & Thai | Prestonpans | "Chen's Chinese Takeaway"; reviews "best Chinese" |
| 123483 | Thai Sun Chinese Take-Away | Glasgow | FB "Chinese Takeaway and Delivery"; review: "more Chinese than thai… only a tiny section of thai food" |
| 1884432 | One Two Chinese & Thai | Falkirk | site/name "One Two Chinese Takeaway"; Just-Eat "Wide selection of Chinese" |
| 1895640 | The Fuchka Man, Halal Thai & Chinese | London E2 | Bangladeshi street-food stall (fuchka) in food court; multi-brand unit |
| 1592739 | Beijing Noodles / 6 other brands | Greenford | 7-brand ghost kitchen; "Thai Street Foods" one of many brands |
| 1721229 | Wraps&Wings/SukhumThai/5 other brands | Putney | 6-brand ghost kitchen; physically Wraps & Wings. Was deliberately allowlisted as SukhumThai — policy now reverses that |

## BORDERLINE — 3 (your call)
| FSA ID | Name | City | Note |
|---|---|---|---|
| 1868586 | Sweet Basil Chinese & Thai | Kirk Hammerton (York) | Family-run dine-in; self-described "Chinese and Thai… 100+ authentic Chinese and Thai dishes" — genuine dual menu |
| 1986142 | TJ's Thai & Chinese | Lerwick | "TJ's Thai and Chinese"; menu has Thai + Chinese sections; often billed "TJ's Thai Restaurant" first |
| 1881809 | Aizah Thai & Cafe / Spicy Wok | London E14 | Thai-branded café; Spicy Wok sub-brand is "Pan-Asian & Thai" (incl. Korean, Indian, bubble tea) |

## KEEP — 6 (Thai-led despite mixed cues in name)
| FSA ID | Name | City | Evidence |
|---|---|---|---|
| 675122 | Thai Oriental | Cleethorpes | Menu in Thai script; "Thai Oriental Mixed Starters"; TA 4.5 | 
| 1882065 | Mum's Thai (Faversham) | Swale | "Experience the Taste of Thailand"; TA 4.9 "authentic Thai cuisine" |
| 1259184 | Thai Wok Noodle Bar | Glossop | "Thai Noodle Bar" branding; Thai dish menu; TA "amazing Thai food" |
| 964056 | Charm (Bath) | Bath | "Charm Thai Restaurant… authentic Thai food"; IG "finest authentic Thai" |
| 1630357 | Wok 'n' Roll Thai Noodle Bar | Llandudno | Just-Eat "Wide selection of Thai"; billed "Thai Noodle Bar" |
| 918730 | Mr Wok Thai Noodle Bar | Plymouth | "authentic Thai Restaurant… #1 rated Thai takeaway 8 years"; Thai street-food menu |

## Removal mechanism (recommended)
- `data/exclusions.json` → `excluded_fsa_ids` (already 101 entries) — honoured by all page generators (restaurant pages, city pages, browse links, sitemaps). Reversible.
- After adding: regenerate pages → verify removed pages pruned, city counts updated, FAQs consistent.
- Alternative (heavy): full removal from restaurants.json like the 216 non-Thai cleanup (previous commit). Only if exclusions prove insufficient.
