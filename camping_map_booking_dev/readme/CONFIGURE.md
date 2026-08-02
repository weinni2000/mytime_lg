This module is meant for one specific database (`lisigruen.at`) and creates
throwaway placeholder zones/pitches, same as `camping_map_booking`'s demo
data - do not install it on a production database that already has its own
camping pitches, it will add 3 unrelated "Pitch A1/B1/C1" products.

After install, replace `camping_map_booking`'s
`static/src/img/camping_map.png` with the real map and recalibrate each
zone's `points` field to match it (see `camping_map_booking`'s own
`readme/CONFIGURE.md`).
