import netCDF4 as nc
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import glob
import os

output_dir = '/wrf/output'
wrfout_files = sorted(glob.glob(f'{output_dir}/wrfout_d01_*'))

if not wrfout_files:
    print("No wrfout files found in /wrf/output/")
    print("Run WRF simulation first, then mount output folder.")
    exit()

for wrfout in wrfout_files:
    print(f"Processing: {wrfout}")
    f = nc.Dataset(wrfout)
    T2    = f.variables['T2'][0, :, :] - 273.15
    U10   = f.variables['U10'][0, :, :]
    V10   = f.variables['V10'][0, :, :]
    XLAT  = f.variables['XLAT'][0, :, :]
    XLONG = f.variables['XLONG'][0, :, :]

    timestamp = os.path.basename(wrfout).replace('wrfout_d01_', '')

    fig, axes = plt.subplots(1, 3, figsize=(18, 5),
                             subplot_kw={'projection': ccrs.PlateCarree()})

    for ax, data, title, cmap, label in zip(
        axes,
        [T2, U10, V10],
        [f'2m Temperature ({timestamp})',
         f'10m U-Wind ({timestamp})',
         f'10m V-Wind ({timestamp})'],
        ['RdYlBu_r', 'coolwarm', 'coolwarm'],
        ['Temperature (°C)', 'U-Wind (m/s)', 'V-Wind (m/s)']
    ):
        cf = ax.contourf(XLONG, XLAT, data, levels=20,
                         cmap=cmap, transform=ccrs.PlateCarree())
        plt.colorbar(cf, ax=ax, label=label)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--')
        ax.add_feature(cfeature.STATES, linewidth=0.3, linestyle=':')
        ax.set_title(title)
        ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)

    out_file = f'{output_dir}/wrf_plot_{timestamp}.png'
    plt.savefig(out_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {out_file}")

print("Done.")
