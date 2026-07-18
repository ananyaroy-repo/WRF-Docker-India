"""
Generates a minimal, technically-valid CAMx Initial Conditions (IC) netCDF file
with uniform "clean troposphere" placeholder concentrations.

Structure verified directly against CAMx v7.32 source:
  - Global attributes: /opt/camx/IO_NCF/ncf_chk_griddef.f
  - NAME attribute check: /opt/camx/IO_NCF/ncf_cncprep.f (expects 'INITIAL')
  - Species variable matching: /opt/camx/IO_NCF/ncf_set_species_mapping.f
    (exact nf_inq_varid match on species name — no case games, no prefix)

NOT independently validated by an actual successful CAMx run yet — this is the
first real attempt, built from source-code reading, not from a working example.
Expect it may need at least one round of fixing based on CAMx's own error output,
same pattern as every other component built this session.

Usage: python3 generate_camx_ic.py d01
"""
import netCDF4 as nc
import numpy as np
import sys

DOMAIN = sys.argv[1] if len(sys.argv) > 1 else 'd01'

# Domain grid parameters — confirmed per-domain from earlier WRFCAMx diagnostic runs.
# dx/dy in km (WRFCAMx convention) get converted to meters for CAMx's IOAPI convention.
DOMAIN_PARAMS = {
    'd01': {'nx': 129, 'ny': 129, 'dx_km': 27.0, 'sw_x_km': -1741.5,     'sw_y_km': -1741.5},
    'd02': {'nx': 99,  'ny': 99,  'dx_km': 9.0,  'sw_x_km': -985.500427, 'sw_y_km': 256.498779},
    'd03': {'nx': 99,  'ny': 99,  'dx_km': 9.0,  'sw_x_km': -958.500061, 'sw_y_km': -1309.50024},
    'd04': {'nx': 99,  'ny': 99,  'dx_km': 9.0,  'sw_x_km': 67.4996414,  'sw_y_km': -337.500977},
}

if DOMAIN not in DOMAIN_PARAMS:
    print(f'Unknown domain: {DOMAIN}')
    sys.exit(1)

p = DOMAIN_PARAMS[DOMAIN]
NLAY = 27  # matches the layer mapping already used for WRFCAMx

# Uniform "clean troposphere" placeholder concentrations (ppm).
# These are NOT measured values — deliberately simple placeholders to let CAMx
# run at all, per the earlier discussion. Adjust if a more realistic starting
# point is wanted later.
SPECIES_VALUES_PPM = {
    'O3':   0.035,    # ~35 ppb, typical clean background
    'NO':   0.0001,
    'NO2':  0.001,
    'CO':   0.100,    # ~100 ppb
    'SO2':  0.0005,
    'PAR':  0.001,    # generic paraffin-carbon placeholder (CB6)
}

out_path = f'camx_ic_{DOMAIN}.nc'
ds = nc.Dataset(out_path, 'w', format='NETCDF3_64BIT_OFFSET')

# ── DIMENSIONS ────────────────────────────────────────────────────────────
ds.createDimension('TSTEP', 1)
ds.createDimension('LAY', NLAY)
ds.createDimension('ROW', p['ny'])
ds.createDimension('COL', p['nx'])
ds.createDimension('VAR', len(SPECIES_VALUES_PPM))
ds.createDimension('DATE-TIME', 2)

# ── GLOBAL ATTRIBUTES — confirmed required by ncf_chk_griddef.f / ncf_cncprep.f ──
ds.CAMx_NAME = 'INITIAL'.ljust(10)
ds.NAME = 'INITIAL'.ljust(10)
ds.ITZON = 0
ds.XCENT = 83.0
ds.YCENT = 21.499985
ds.IUTM = 0
ds.XORIG = p['sw_x_km'] * 1000.0   # km -> m
ds.YORIG = p['sw_y_km'] * 1000.0
ds.XCELL = p['dx_km'] * 1000.0
ds.YCELL = p['dx_km'] * 1000.0
ds.CPROJ = 5   # Mercator, confirmed from ncf_chk_griddef.f
ds.GDTYP = 7   # Mercator, confirmed from ncf_chk_griddef.f

# ── TFLAG (standard IOAPI time-flag variable, CAMx expects this to exist) ──
tflag = ds.createVariable('TFLAG', 'i4', ('TSTEP', 'VAR', 'DATE-TIME'))
tflag[0, :, 0] = 2023198   # YYYYDDD for 2023-07-17 — matches your actual run start
tflag[0, :, 1] = 0          # HHMMSS — hour 0

# ── SPECIES VARIABLES — one per species, exact-name match per ncf_set_species_mapping.f ──
for spec, val_ppm in SPECIES_VALUES_PPM.items():
    var = ds.createVariable(spec, 'f4', ('TSTEP', 'LAY', 'ROW', 'COL'))
    var[:] = np.full((1, NLAY, p['ny'], p['nx']), val_ppm, dtype='f4')
    var.units = 'ppm'.ljust(16)
    var.long_name = spec.ljust(16)

ds.close()
print(f'Wrote {out_path}')
print(f'  Domain: {DOMAIN}  ({p["nx"]}x{p["ny"]}, {NLAY} layers, {p["dx_km"]}km)')
print(f'  Species: {list(SPECIES_VALUES_PPM.keys())}')
