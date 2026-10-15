# Leeds Pilot — Missing Thai Venues Discovery (OSM → FSA → Web verify)

Date: 2026-10-15 · Status: FOR REVIEW (nothing added to site/data yet)
Policy update (2026-10-15): **authentic Thai only** — Chinese/Hong Kong/etc. hybrids excluded.

## Method validated
1. OSM Overpass: Leeds-bbox venues tagged `cuisine~thai` (restaurant/cafe/fast_food/pub/bar) → 44 found, 26 not matched to our data
2. FSA API: name search + LocalAuthorityName=Leeds filter + address/postcode search → resolved existence, rename and staleness
3. Web verification per surviving candidate

## A. Real Thai, awaiting FSA inspection → cannot list yet
| Venue | FSA ID | Address | Note |
|---|---|---|---|
| Siam Corner | 1917318 | Guiseley LS20 8BX | Authentic Thai + breakfast café; Instagram/UberEats/TripAdvisor active. **No 'thai' in name → needs NON_CHAIN_THAI watchlist add to auto-enter once rated** |
| Go Thai Bistro | 1963666 | 86 New Road Side, Horsforth LS18 4QB | will auto-enter when rated (name contains 'Thai') |
| Mekhong River Thai Kitchen | 1980109 | 201 Lower Wortley Rd LS12 4PX | will auto-enter when rated (name contains 'Thai'); OSM has old name "Ban Thai" |

## B. Rejected / resolved (no action)
- Dragon City (Otley) — Chinese takeaway (TripAdvisor/Facebook) — OSM tag inaccurate
- Tasty Flavour (Bramley LS13) — Chinese takeaway (listings/reviews)
- **Hong Kong Super Cook (Horsforth + Otley) — REJECTED per authentic-Thai policy: Chinese/Thai hybrid**
- Panku Streetfood — Asda supermarket counter, not a Thai restaurant
- Nan's Thai Cafe (Hyde Park) — address now Chick 'N' Bao; OSM stale
- Baan Thai Restaurant (Morley LS27) — unit now Juicy African Kitchen; OSM stale
- Yum Yum Thai (Wetherby) — former name of Baanrai Thai Cafe (already listed); OSM stale
- Just Thai (Wakefield), Thai Corner (Halifax) — outside Leeds district
- Enthaice, Muang Loei, Cafe Thai ×2, Sukothai ×2, Nat Pad Thai — already in our data
- Kann (Seacroft LS14 6LB) — listed by some directories as Thai; **no FSA record** at address; cannot list
- Keyword sweep (siam/bangkok/khao/baan/sabai/isaan/somtam/krua/sawadee/jasmine/chang): only extra find was Siam Corner; rest noise or known

## C. Pub harvest — FSA type 7843 (Pub/bar/nightclub)
Discovery patterns (verified with live examples):
- **Pattern 1 (invisible to pipeline)**: kitchen rides on the pub's registration, typed pub, no Thai signal in name — e.g. *Mae Tic Kitchen At Hare And Hounds* (Brighton). Only findable via OSM/web discovery
- **Pattern 2 (harvestable)**: kitchen named but typed as pub — our fetches never include type 7843. Harvested nationally: **26 clean pub-typed Thai-signal records** (hybrid cues excluded):

| FHRSID | Name | Rating | Area |
|---|---|---|---|
| 1859525 | Thai Restaurant At The Old House At Home | ★5 | Basingstoke |
| 1829347 | Fat Cat Thai Kitchen At The Dover Castle | ★5 | Brighton |
| 479310 | Keng's Thai Kitchen At Longman Of Wilmington | ★5 | Brighton |
| 1837731 | Mu Ban Thai Foods At The Village | ★4 | Brighton |
| 1885056 | Thai Golden Elephant At Regency Tavern | ★4 | Brighton |
| 1809849 | Thai Zaab At The Mucky Duck | ★5 | Brighton |
| 672376 | Aston Fields Club Thai | Exempt | Bromsgrove |
| 1919502 | Cricketers Thai Ltd | ★5 | Cambridge |
| 147926 | Nava Thai | ★5 | Chichester |
| 913301 | Thai Orchid & Murray Arms | Pass | Dumfries & Galloway |
| 1208931 | Sabai @ George & Dragon | ★3 | Ealing |
| 336627 | Thai Plough | ★5 | East Cambridgeshire |
| 1893402 | Thai Nawa | Awaiting insp | Hillingdon |
| 1386274 | Kai's Thai Food @ The Cocoanut | ★4 | Kingston |
| 1951936 | Seaford Thai Kitchen | ★4 | Lewes |
| 1992462 | Village Thai kitchen | Awaiting insp | Manchester |
| 556307 | Queens Head And Thai Rice Restaurant | ★5 | Newark & Sherwood |
| 18040 | The Vine Thai Cuisine | ★4 | Norwich |
| 479096 | Drovers Thai Restaurant | ★3 | Powys |
| 1437298 | Lion Thai Restaurant @ The Red Lion | ★5 | Reigate & Banstead |
| 1662287 | Thai @The Albert | ★5 | Richmond |
| 1974463 | Pad thai boys | Awaiting insp | Southwark |
| 1703936 | London Road Ale House / Thai Wai | ★3 | Stoke-on-Trent |
| 514135 | The North Star & Thai Kitchen | ★5 | Waltham Forest |
| 1910000 | Pad Thai Boys (Cheshire Cheese) | ★3 | Westminster |
| 283051 | The Red Lion - Pad Thai | ★5 | Wokingham |

- **Leeds pub pass: 0 pub-typed Thai-signal records.** Leeds' only Thai-in-pub = The Old Peacock / Noi's Thai Kitchen; Noi's has its own separate takeaway-type registration (already listed). Old Peacock pub record exists (615896, ★5) — would be the pub-section entry ("Thai food by Noi's Thai Kitchen at The Old Peacock")

## D. Existing-data audit — hybrid entries (policy question for Johnny)
**23 entries in current data hit hybrid cues** (chinese/oriental/wok/etc.); after removing false positives ("Tasty Thai…"), ~18 are genuine Chinese/Thai hybrids, e.g.:
- Golden Fields Chinese & Thai (Manchester), Beijing Chinese & Thai (Bristol), Chens Chinese & Thai (East Lothian), Thai Sun Chinese Take-Away (Glasgow), One Two Chinese & Thai (Falkirk), Sweet Basil Chinese & Thai (York), Charm Oriental Bar & Thai (Bath), Honeymoon Chinese And Thai (Devon), TJ's Thai & Chinese (Shetland), Wok 'n' Roll Thai Noodle Bar (Conwy), Mr Woks Thai Noodle (Plymouth), Oriental Hub/Kings Of Thai (Rushmoor), etc.
- **Question**: remove these from the live site (changes city counts + pages), or apply the authentic-Thai policy to new additions only?

## E. Recommended next actions
1. Add "Siam Corner" to `NON_CHAIN_THAI` list in fetch_all_thai_data.py (watches until FSA rates it)
2. Add FSA type 7843 to the Thai-keyword fetches → harvests the 26 pub records above (needs a 'pub' entry type + pub section UI)
3. Standing watchlist policy: any verified Thai venue awaiting inspection → add to NON_CHAIN_THAI immediately
4. **Decision needed**: existing hybrid entries (Section D)
5. Roll pattern to next city (Manchester / Birmingham) once approved
6. Optional: fix stale OSM entries upstream (Nan's, Ban Thai name, Baan Thai Morley, Yum Yum Thai)
