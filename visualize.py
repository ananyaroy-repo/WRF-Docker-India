import netCDF4 as nc
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature

configs = [
    (
        '/wrf/user-config/geo_em.d01.nc',
        'Terrain Height — WRF Domain d01 (27km, All India)',
        '/wrf/output/terrain_plot_d01.png'
    ),
    (
        '/wrf/user-config/geo_em_9km_delhi.nc',
        'Terrain Height — WRF Domain d02 (9km, Delhi Region)',
        '/wrf/output/terrain_plot_d02.png'
    ),
    (
        '/wrf/user-config/geo_em_3km_delhi_city.nc',
        'Terrain Height — WRF Domain d03 (3km, Delhi City)',
        '/wrf/output/terrain_plot_d03.png'
    ),
    (
        '/wrf/user-config/geo_em_3km_mumbai.nc',
        'Terrain Height — WRF Domain d04 (3km, Mumbai)',
        '/wrf/output/terrain_plot_d04.png'
    ),
]

for nc_file, title, out_file in configs:
    print(f"Processing: {title}")
    try:
        f = nc.Dataset(nc_file)
        HGT   = f.variables['HGT_M'][0, :, :]
        XLAT  = f.variables['XLAT_M'][0, :, :]
        XLONG = f.variables['XLONG_M'][0, :, :]
        print(f"  Grid shape: {HGT.shape}")
        print(f"  Elevation range: {HGT.min():.1f} — {HGT.max():.1f} m")

        fig, ax = plt.subplots(figsize=(8, 6),
                               subplot_kw={'projection': ccrs.PlateCarree()})
        cf = ax.contourf(XLONG, XLAT, HGT,
                         levels=30, cmap='terrain',
                         transform=ccrs.PlateCarree())
        plt.colorbar(cf, ax=ax, label='Elevation (m)')
        ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--')
        ax.add_feature(cfeature.STATES, linewidth=0.3, linestyle=':')
        ax.set_title(title)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)
        plt.savefig(out_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved: {out_file}")
    except FileNotFoundError:
        print(f"  Skipped (file not found): {nc_file}")

print("Done.")
