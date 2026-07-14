import netCDF4 as nc
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import glob, os, re, sys

DOMAIN = sys.argv[1] if len(sys.argv) > 1 else 'd01'
DATA_DIR = '/data'
OUT_DIR = '/output'
os.makedirs(OUT_DIR, exist_ok=True)

files = sorted(glob.glob(f'{DATA_DIR}/wrfout_{DOMAIN}_*'))
if not files:
    print(f'No wrfout files found for domain {DOMAIN}')
    sys.exit(1)
print(f'Found {len(files)} files for {DOMAIN}')

domain_mean_t2 = []
domain_total_precip_interval = []
timestamps = []
prev_rain = None
new_images = 0
skipped_images = 0

for i, fpath in enumerate(files):
    fname = os.path.basename(fpath)
    tstamp = fname.split(f'{DOMAIN}_')[1]

    ds = nc.Dataset(fpath)
    if ds.dimensions['Time'].size == 0:
        print(f'  SKIPPING {fname}: Time dimension is 0 (likely an incomplete write) — no data to plot')
        ds.close()
        continue
    T2 = ds.variables['T2'][0, :, :] - 273.15
    U10 = ds.variables['U10'][0, :, :]
    V10 = ds.variables['V10'][0, :, :]
    RAINC = ds.variables['RAINC'][0, :, :]
    RAINNC = ds.variables['RAINNC'][0, :, :]
    XLAT = ds.variables['XLAT'][0, :, :]
    XLONG = ds.variables['XLONG'][0, :, :]
    ds.close()

    total_rain = RAINC + RAINNC
    if prev_rain is None:
        interval_rain = total_rain.copy()
    else:
        interval_rain = total_rain - prev_rain
        interval_rain[interval_rain < 0] = 0
    prev_rain = total_rain

    domain_mean_t2.append(np.mean(T2))
    domain_total_precip_interval.append(np.mean(interval_rain))
    timestamps.append(tstamp)

    out_path = f'{OUT_DIR}/wrf_met_{DOMAIN}_{tstamp.replace(":","-")}.png'

    if os.path.exists(out_path):
        skipped_images += 1
        continue

    print(f'Rendering {fname} ...')
    fig, axes = plt.subplots(1, 2, figsize=(16, 7),
                              subplot_kw={'projection': ccrs.PlateCarree()})

    ax = axes[0]
    cf = ax.contourf(XLONG, XLAT, T2, levels=25, cmap='RdYlBu_r',
                      transform=ccrs.PlateCarree())
    step = max(1, XLAT.shape[0] // 20)
    ax.quiver(XLONG[::step, ::step], XLAT[::step, ::step],
              U10[::step, ::step], V10[::step, ::step],
              transform=ccrs.PlateCarree(), scale=200, width=0.002)
    plt.colorbar(cf, ax=ax, label='2m Temperature (°C)', fraction=0.046)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--')
    ax.set_title(f'{DOMAIN} — T2 & 10m wind — {tstamp}')
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)
    gl.right_labels = False

    ax2 = axes[1]
    cf2 = ax2.contourf(XLONG, XLAT, interval_rain, levels=20, cmap='Blues',
                        transform=ccrs.PlateCarree())
    plt.colorbar(cf2, ax=ax2, label='Precip this interval (mm)', fraction=0.046)
    ax2.add_feature(cfeature.COASTLINE, linewidth=0.8)
    ax2.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--')
    ax2.set_title(f'{DOMAIN} — Precipitation — {tstamp}')
    gl2 = ax2.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)
    gl2.right_labels = False

    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches='tight')
    plt.close()
    new_images += 1
    print(f'  Saved: {out_path}')

print(f'New images: {new_images}, skipped (already existed): {skipped_images}')

# Summary plot always regenerates — cheap, and needs to reflect the latest full timestep set
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
ax1.plot(range(len(timestamps)), domain_mean_t2, marker='o', color='crimson')
ax1.set_ylabel('Domain-mean T2 (°C)')
ax1.set_title(f'{DOMAIN} — Domain-mean 2m temperature over time')
ax1.grid(alpha=0.3)

ax2.bar(range(len(timestamps)), domain_total_precip_interval, color='steelblue')
ax2.set_ylabel('Mean precip / interval (mm)')
ax2.set_xticks(range(len(timestamps)))
ax2.set_xticklabels(timestamps, rotation=45, ha='right', fontsize=8)
ax2.grid(alpha=0.3)

plt.tight_layout()
summary_path = f'{OUT_DIR}/wrf_timeseries_summary_{DOMAIN}.png'
plt.savefig(summary_path, dpi=130, bbox_inches='tight')
plt.close()
print(f'Saved summary: {summary_path}')
print('Done.')
