"""
Sanity-check script for a synthetic CAMx IC file (generate_camx_ic.py output).

This is deliberately NOT a geographic visualization — every value in the file
is a uniform constant by design, so a map would just be one flat color and
wouldn't tell you anything real. Instead, this checks the things that could
actually be wrong: correct shape, correct value, no NaN, no accidental zeros.

Usage: python3 check_camx_ic.py camx_ic_d01.nc
"""
import netCDF4 as nc
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys

FILE = sys.argv[1] if len(sys.argv) > 1 else 'camx_ic_d01.nc'
OUT_PNG = FILE.replace('.nc', '_shapecheck.png')

ds = nc.Dataset(FILE)

print(f'=== {FILE} ===')
print(f'Global attrs: XORIG={ds.XORIG}, YORIG={ds.YORIG}, XCELL={ds.XCELL}, '
      f'YCELL={ds.YCELL}, CPROJ={ds.CPROJ}, GDTYP={ds.GDTYP}')
print(f'Grid: {ds.dimensions["COL"].size} x {ds.dimensions["ROW"].size}, '
      f'{ds.dimensions["LAY"].size} layers')
print()

species_vars = [v for v in ds.variables if v not in ('TFLAG',)]
print(f'{"Species":<8} {"Min":>10} {"Max":>10} {"Mean":>10} {"Has NaN":>8} {"All-zero":>9}')
for spec in species_vars:
    data = ds.variables[spec][:]
    has_nan = bool(np.isnan(data).any())
    all_zero = bool(np.all(data == 0))
    print(f'{spec:<8} {np.min(data):>10.5f} {np.max(data):>10.5f} '
          f'{np.mean(data):>10.5f} {str(has_nan):>8} {str(all_zero):>9}')

# Simple shape-check plot: surface layer, first species, plain grid indices
# (no lat/lon, no coastlines — just confirms the array shape/fill is sane)
first_spec = species_vars[0]
surface = ds.variables[first_spec][0, 0, :, :]

fig, ax = plt.subplots(figsize=(7, 6))
im = ax.imshow(surface, origin='lower', cmap='viridis')
plt.colorbar(im, ax=ax, label=f'{first_spec} (ppm)')
ax.set_xlabel('COL index')
ax.set_ylabel('ROW index')
ax.set_title(f'{FILE} — {first_spec}, surface layer\n(uniform by design — confirms shape/fill only, not real spatial data)')
plt.tight_layout()
plt.savefig(OUT_PNG, dpi=120)
plt.close(fig)
print(f'\nSaved shape-check plot: {OUT_PNG}')

ds.close()
