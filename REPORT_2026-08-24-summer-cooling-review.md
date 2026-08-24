# Summer Cooling Review — 2026-08-24

A review of the first nights of the Vallox nocturnal-cooling integration, the
house's heat behaviour on a hot day, and the resulting decisions on where to
spend effort next. Data from the `~/vallox-logs/` logger and live HA states.

## TL;DR

- The nocturnal-cooling integration is **reliable** (5/5 nights, clean engage/
  revert, readback-verified) and the **mechanism works** — it delivers 15–19 °C
  supply air in full bypass vs ~20 °C on commissioned heat-recovery nights.
- But the **room-temperature impact is modest and noisy**: ~0.1–0.5 °C
  overnight, comparable to commissioned behaviour, because the house's thermal
  mass >> the MVHR airflow. Ventilation is a small heat-removal path.
- On a 34 °C day the house only rose ~1 °C (well defended), but it **peaks in the
  evening**, not the afternoon — the roof/walls release absorbed solar with a
  ~6 h lag. The bedrooms are warmest exactly at bedtime.
- **The heat is not coming through the windows.** With upstairs blinds closed,
  the top floor warmed as much as the ground floor with sun through its
  windows — the top-floor gain is the **roof**, not glazing.
- Decisions: keep **passive attic ventilation** (biggest top-floor lever,
  PV untouched), a **bedroom split AC** is a realistic top-up for bedtime, **no**
  to awnings-over-blinds (wrong target), and we built a **heat-avoidance
  automation** that throttles the MVHR when outdoor > indoor.

---

## 1. Nocturnal-cooling integration — 5 nights, Aug 19–23

Every night: engaged ~22:00 (Away, 60 % fan, H7→5, away-target→8, full bypass),
reverted ~05:00 (H7→15, away-target→20, profile→base). Readback-verified, no
errors in automation traces, unit always back to a safe normal state.

| night | out_min | H7 | fan% | cell | supply °C | extract Δ | room Δ (avg) |
|---|---|---|---|---|---|---|---|
| 19 (mild) | 16.4 | 5 | 60 | full bypass | 18.8 | −0.1 | −0.01 |
| 20 | 11.5 | 5 | 60 | bypass + 61 min HR¹ | 17.0 | −0.5 | −0.48 |
| 21 | 15.4 | 5 | 60 | bypass + 22 min HR¹ | 19.0 | −0.4 | −0.50 |
| 22 | 12.4 | 5 | 60 | bypass + 61 min HR¹ | 17.0 | −0.4 | −0.13 |
| 23 (cold) | 8.5 | 5 | 60 | bypass + 61 min HR¹ | 15.1 | −0.7 | −0.45 |

¹ HR = heat recovery, appears only *after* the 05:00 revert when H7 jumps back
to 15 and the cutoff returns to 15.7 °C (outdoor is then below it). Supply
reached **13.4 °C** on night 23 — well below the 15 °C defrost setting, so the
defrost entity is **not** limiting cooling.

**Comparison vs commissioned cool nights (epoch B, H7=15):** nights 13/14
delivered 20–20.6 °C supply in mostly heat-recovery and still cooled rooms
~0.55 °C. Integration nights cool ~0.1–0.5 °C with 15–17 °C supply. The supply
air is clearly colder (~4–5 °C), but room cooling is **not clearly better** —
deltas are within occupancy/internal-gain noise (one night the master bedroom
*rose* +0.18 °C from people, the office +0.40 °C from a computer).

**Conclusion:** the integration does exactly what it was built to do — keep
the unit in free-cooling bypass on summer nights instead of heat-recovering.
But the MVHR moves a few hundred m³/h against a thermal mass of tens of
kWh/°C, so the net room effect is ~0.5 °C at best. It's a "don't let the unit
heat-recover at night" lever, not a "cool the house" lever.

**Finding to harden (not yet done):** the profile snapshot uses
`coordinator.data.profile`, which returns BOOST when a boost timer is active.
If a coincidental boost is running when cooling starts, `stop` would call
`set_profile(BOOST)` and re-engage a timed boost after cooling. Last night it
worked (snapshot caught the base profile), partly by luck. Fix: snapshot the
base profile from `A_CYC_STATE` (0=Home/1=Away/2=Auto) instead. Small change in
`services.py`, with a test.

---

## 2. Hot-day behaviour — Aug 15 (outdoor 14 → 34 → 24 °C)

Per floor (CEST, mean):

| | 06–08 | 14–16 | 20–22 |
|---|---|---|---|
| outdoor | 21.5 | 33.9 | 25.7 |
| **Top (timber)** | 23.4 | 23.7 | **24.5** |
| Ground | 23.3 | 23.6 | 24.0 |
| Basement | 21.6 | 21.6 | 21.5 |

Two facts:

1. **The house is well defended** — only ~+1 °C on a 34 °C day (basement flat).
2. **Indoor peaks in the evening, not the afternoon.** Outdoor maxed at 15:00
   and was already 25.7 °C by 21:00, yet every room is warmer at 20–22:00 than
   at 14–16:00. This is thermal-mass time-lag: the roof/walls absorb solar all
   day and release it inward ~6 h later — which is why the bedrooms are warmest
   at bedtime. The evening peak is concentrated in the west rooms (living,
   kitchen) and the top floor (Kato 24.9).

---

## 3. Where the heat is actually coming from

**The key comparison** — top floor has blinds closed all day, ground floor's
west windows are exposed until 16:00:

| | rise, morning → evening (Aug 15) |
|---|---|
| Top floor (**blinds closed**) | **+1.0 °C** (Kato +1.2, bad_og +1.3, master +0.9) |
| Ground floor (windows exposed) | **+0.9 °C** (living +1.2, kitchen +0.9) |

The top floor — windows already shaded — warmed just as much as the ground
floor with sun pouring through its windows. **The top-floor gain is the roof,
not the glazing.** More window shading upstairs would do almost nothing.

Heat flow per m² (rough, hot sunny day):

| path | W/m² | note |
|---|---|---|
| Window, unshaded | ~400 | g≈0.5 × ~800 W/m² sun |
| Window, internal blind closed | ~150–250 | blind heats, re-radiates inward |
| Window, external awning | ~80–120 | beam stopped before glass |
| Opaque insulated wall | ~5 | surface ~50 °C, U≈0.2 |
| Opaque roof | ~5–6 | surface ~60 °C, but large area → dominates |

Per m² an opaque wall passes ~30–50× less than a window. The facade is not the
villain. The two big opaque sources are the **roof** (large area, intense sun,
PV-untouchable) and the **windows where the geometry fails** (low evening sun
under the horizontal Markisen). The low-angle west sun bypassing the awning
is a real, measured contributor to the evening peak in living/kitchen.

**Conclusion:** don't invest in awnings over already-blinded windows — wrong
target, diminishing returns. The facade opaque gain is small and only
fixable by external insulation (major) or reflective render (modest) — not
worth it. The roof is the main top-floor input and can't be coated (PV).

---

## 4. A daytime gain we can control: the MVHR itself

On Aug 15 the Vallox supply air was **24–27 °C from ~09:00–21:00** while indoor
was ~23 °C. Once outdoor > indoor, even heat-recovering, the MVHR supplies air
warmer than the house — roughly **0.2–0.3 kW of heat pumped in for ~12 h**.
Not the dominant gain, but real and *software-controllable*.

**Built:** `automation.vallox_heat_avoidance` (blueprint
`roelven/vallox_heat_avoidance.yaml`, committed). Drops `fan.vallox` to 25 %
when outdoor > indoor + 1 °C, restores 45 % when outdoor < indoor. Guarded to
the Home preset so it never fights the nocturnal-cooling (Away) automation.
CO2 control still raises the fan if air quality demands. It's the daytime twin
of the night cooling.

---

## 5. Decisions

1. **Passive attic ventilation — keep, do first.** The attic is a sealed cold
   cavity (insulation on the OG ceiling), so its 55–65 °C air is what drives
   heat down into the bedrooms. Flushing it to near-outdoor via soffit inlets +
   gable/ridge outlet collapses the ΔT across the OG ceiling from ~35 K to
   ~7 K — roughly a **5–7× cut** in the downward heat flow, for a few hundred
   €, **PV untouched** (work is at the gable/soffit, not the roof pans). The
   biggest cost-effective top-floor lever available. *(Mechanical attic fan
   removed as an option — passive only.)*

2. **Bedroom split AC for the top floor — realistic, as a targeted top-up.**
   The floor cooling is hydronic, capped at ~18 °C floor surface (~20–40 W/m²,
   slow) and can't beat the lagged evening gain. A split delivers 1–3 kW of
   chilled air on demand — the right tool for warm bedrooms at bedtime. Run
   only evenings (room > 23 °C, ~19:00–02:00), modest setpoint 22–23 °C:
   ~1–3 kWh/room/hot-night. It complements the floor cooling + MVHR + attic
   vent, doesn't replace them. Do attic vent first; add the split if bedrooms
   are still warm.

3. **Awnings over closed blinds — no.** Windows aren't the top-floor problem
   (the roof is), and downstairs the awnings are already there — the residual
   is low-angle geometry, which awnings don't fix.

4. **Facade opaque gain — not worth treating.** Small per m²; only major
   renovation would cut it.

---

## 6. Open items

- Implement the snapshot-base-profile hardening (§1) so a coincidental boost at
  start can't be "restored" after cooling.
- Verify on the next warm day that the floor loop reaches ~18 °C
  (`sensor.luxtronik_…_flow_out_temperature`) — confirms cooling is delivering
  its rated capacity and the gain simply exceeds it.
- If passive attic vents are installed, re-measure the top-floor evening peak
  to quantify the gain reduction; add a bedroom split only if still needed.