import netCDF4 as nc
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import glob, os, sys

DOMAIN = sys.argv[1] if len(sys.argv) > 1 else 'd01'
DATA_DIR = f'/data/camx_input_{DOMAIN}'
OUT_DIR = f'/output'
os.makedirs(OUT_DIR, exist_ok=True)

LU_FILE  = f'{DATA_DIR}/camx.lu.{DOMAIN}.nc'
D2_FILE  = f'{DATA_DIR}/camx.2d.{DOMAIN}.nc'
D3_FILE  = f'{DATA_DIR}/camx.3d.{DOMAIN}.nc'
KV_FILE  = f'{DATA_DIR}/camx.kv.{DOMAIN}.nc.YSU'

for f in [LU_FILE, D2_FILE, D3_FILE, KV_FILE]:
    if not os.path.exists(f):
        print(f'MISSING REQUIRED FILE: {f}')
        sys.exit(1)

new_images = 0
skipped_images = 0


def tflag_to_labels(ds):
    """Decode CAMx/IOAPI TFLAG (YYYYDDD, HHMMSS) into readable date-time strings."""
    tflag = ds.variables['TFLAG'][:, 0, :]  # (TSTEP, 2) using first VAR's flag
    labels = []
    for t in range(tflag.shape[0]):
        yyyyddd = int(tflag[t, 0])
        hhmmss  = int(tflag[t, 1])
        year = yyyyddd // 1000
        doy  = yyyyddd % 1000
        hour = hhmmss // 10000
        from datetime import datetime, timedelta
        dt = datetime(year, 1, 1) + timedelta(days=doy - 1, hours=hour)
        labels.append(dt.strftime('%Y-%m-%d_%H:00'))
    return labels


def save_or_skip(fig, out_path):
    global new_images, skipped_images
    if os.path.exists(out_path):
        skipped_images += 1
        plt.close(fig)
        return
    fig.savefig(out_path, dpi=130, bbox_inches='tight')
    plt.close(fig)
    new_images += 1
    print(f'  Saved: {out_path}')


# ── 1. STATIC LU / TOPO MAP ──────────────────────────────────────────────────
def plot_lu_topo():
    out_path = f'{OUT_DIR}/wrfcamx_{DOMAIN}_lu_topo.png'
    if os.path.exists(out_path):
        global skipped_images
        skipped_images += 1
        return
    ds = nc.Dataset(LU_FILE)
    lon = ds.variables['longitude'][:, :]
    lat = ds.variables['latitude'][:, :]
    topo = ds.variables['topo'][0, 0, :, :]

    lu_vars = ['water','ice','lake','eneedl','ebroad','dneedl','dbroad','tbroad',
               'ddecid','eshrub','dshrub','tshrub','sgrass','lgrass','crops','rice',
               'sugar','maize','cotton','icrops','urban','tundra','swamp','desert',
               'mwood','tforest']
    stack = np.stack([ds.variables[v][0, 0, :, :] for v in lu_vars if v in ds.variables], axis=0)
    dominant_idx = np.argmax(stack, axis=0)
    ds.close()

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), subplot_kw={'projection': ccrs.PlateCarree()})
    cf = axes[0].contourf(lon, lat, topo, levels=25, cmap='terrain', transform=ccrs.PlateCarree())
    plt.colorbar(cf, ax=axes[0], label='Topography (m)', fraction=0.046)
    axes[0].add_feature(cfeature.COASTLINE, linewidth=0.8)
    axes[0].add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--')
    axes[0].set_title(f'{DOMAIN} — WRFCAMx Topography')
    gl = axes[0].gridlines(draw_labels=True, linewidth=0.3, alpha=0.5); gl.right_labels = False

    cf2 = axes[1].pcolormesh(lon, lat, dominant_idx, cmap='tab20', transform=ccrs.PlateCarree())
    plt.colorbar(cf2, ax=axes[1], label='Dominant LU category index', fraction=0.046)
    axes[1].add_feature(cfeature.COASTLINE, linewidth=0.8)
    axes[1].add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--')
    axes[1].set_title(f'{DOMAIN} — Dominant Land-Use Category')
    gl2 = axes[1].gridlines(draw_labels=True, linewidth=0.3, alpha=0.5); gl2.right_labels = False

    plt.tight_layout()
    save_or_skip(fig, out_path)


# ── 2. 2D SURFACE TIME SERIES ─────────────────────────────────────────────────
def plot_2d_surface():
    ds = nc.Dataset(D2_FILE)
    lon = ds.variables['longitude'][:, :]
    lat = ds.variables['latitude'][:, :]
    labels = tflag_to_labels(ds)
    n_t = len(labels)

    pblwrf_mean, pblysu_mean = [], []

    for t in range(n_t):
        tstamp = labels[t]
        out_path = f'{OUT_DIR}/wrfcamx_{DOMAIN}_2d_{tstamp.replace(":","-")}.png'

        t2   = ds.variables['t2'][t, 0, :, :] - 273.15
        u10  = ds.variables['u10'][t, 0, :, :]
        v10  = ds.variables['v10'][t, 0, :, :]
        prec = ds.variables['preciprate'][t, 0, :, :]
        pblwrf_mean.append(np.mean(ds.variables['pblwrf'][t, 0, :, :]))
        pblysu_mean.append(np.mean(ds.variables['pblysu'][t, 0, :, :]))

        if os.path.exists(out_path):
            global skipped_images
            skipped_images += 1
            continue

        fig, axes = plt.subplots(1, 2, figsize=(16, 7), subplot_kw={'projection': ccrs.PlateCarree()})
        cf = axes[0].contourf(lon, lat, t2, levels=25, cmap='RdYlBu_r', transform=ccrs.PlateCarree())
        step = max(1, lat.shape[0] // 20)
        axes[0].quiver(lon[::step, ::step], lat[::step, ::step],
                        u10[::step, ::step], v10[::step, ::step],
                        transform=ccrs.PlateCarree(), scale=200, width=0.002)
        plt.colorbar(cf, ax=axes[0], label='T2 (°C)', fraction=0.046)
        axes[0].add_feature(cfeature.COASTLINE, linewidth=0.8)
        axes[0].add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--')
        axes[0].set_title(f'{DOMAIN} WRFCAMx — T2 & 10m wind — {tstamp}')
        gl = axes[0].gridlines(draw_labels=True, linewidth=0.3, alpha=0.5); gl.right_labels = False

        cf2 = axes[1].contourf(lon, lat, prec, levels=20, cmap='Blues', transform=ccrs.PlateCarree())
        plt.colorbar(cf2, ax=axes[1], label='Precip rate (mm/hr)', fraction=0.046)
        axes[1].add_feature(cfeature.COASTLINE, linewidth=0.8)
        axes[1].add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--')
        axes[1].set_title(f'{DOMAIN} WRFCAMx — Precipitation rate — {tstamp}')
        gl2 = axes[1].gridlines(draw_labels=True, linewidth=0.3, alpha=0.5); gl2.right_labels = False

        plt.tight_layout()
        save_or_skip(fig, out_path)

    # PBL comparison line plot (always regenerated — cheap, needs full current dataset)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(range(n_t), pblwrf_mean, marker='o', label='pblwrf (WRF native PBLH)', color='steelblue')
    ax.plot(range(n_t), pblysu_mean, marker='s', label='pblysu (YSU-recomputed)', color='crimson')
    ax.set_ylabel('Domain-mean PBL height (m)')
    ax.set_xticks(range(n_t))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
    ax.set_title(f'{DOMAIN} — PBL height: WRF native vs WRFCAMx YSU-recomputed')
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(f'{OUT_DIR}/wrfcamx_{DOMAIN}_pbl_comparison.png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {OUT_DIR}/wrfcamx_{DOMAIN}_pbl_comparison.png')

    ds.close()


# ── 3. Kv HOVMOLLER (layer vs time, domain-mean) ─────────────────────────────
def plot_kv_hovmoller():
    ds = nc.Dataset(KV_FILE)
    labels = tflag_to_labels(ds)
    kv = ds.variables['kv'][:, :, :, :]  # (TSTEP, LAY, ROW, COL)
    ds.close()

    domain_mean_kv = np.mean(kv, axis=(2, 3))  # (TSTEP, LAY)

    fig, ax = plt.subplots(figsize=(12, 7))
    im = ax.pcolormesh(range(len(labels)), range(1, kv.shape[1] + 1),
                        domain_mean_kv.T, cmap='viridis', shading='auto')
    ax.invert_yaxis()
    plt.colorbar(im, ax=ax, label='Kv (m²/s), domain mean')
    ax.set_ylabel('CAMx layer (1 = surface)')
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
    ax.set_title(f'{DOMAIN} — YSU Vertical Diffusivity (Kv) — layer vs time')
    plt.tight_layout()
    plt.savefig(f'{OUT_DIR}/wrfcamx_{DOMAIN}_kv_hovmoller.png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {OUT_DIR}/wrfcamx_{DOMAIN}_kv_hovmoller.png')


# ── 4. 3D FIELDS: surface-layer maps + Hovmoller profiles ───────────────────
def plot_3d_fields():
    ds = nc.Dataset(D3_FILE)
    lon = ds.variables['longitude'][:, :]
    lat = ds.variables['latitude'][:, :]
    labels = tflag_to_labels(ds)
    n_t = len(labels)
    n_lay = ds.dimensions['LAY'].size

    temp_all = ds.variables['temperature'][:, :, :, :]  # (TSTEP, LAY, ROW, COL)
    uwind_all = ds.variables['uwind'][:, :, :, :]
    vwind_all = ds.variables['vwind'][:, :, :, :]
    ds.close()

    # -- surface layer (layer 0) maps --
    for t in range(n_t):
        tstamp = labels[t]
        out_path = f'{OUT_DIR}/wrfcamx_{DOMAIN}_3dsfc_{tstamp.replace(":","-")}.png'
        if os.path.exists(out_path):
            global skipped_images
            skipped_images += 1
            continue

        temp_sfc = temp_all[t, 0, :, :] - 273.15
        u_sfc = uwind_all[t, 0, :, :]
        v_sfc = vwind_all[t, 0, :, :]

        fig = plt.figure(figsize=(9, 7))
        ax = plt.axes(projection=ccrs.PlateCarree())
        cf = ax.contourf(lon, lat, temp_sfc, levels=25, cmap='RdYlBu_r', transform=ccrs.PlateCarree())
        step = max(1, lat.shape[0] // 20)
        ax.quiver(lon[::step, ::step], lat[::step, ::step],
                  u_sfc[::step, ::step], v_sfc[::step, ::step],
                  transform=ccrs.PlateCarree(), scale=200, width=0.002)
        plt.colorbar(cf, ax=ax, label='Surface-layer temperature (°C)', fraction=0.046)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, linestyle='--')
        ax.set_title(f'{DOMAIN} WRFCAMx 3D — Layer 1 (surface) T & wind — {tstamp}')
        gl = ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5); gl.right_labels = False
        plt.tight_layout()
        save_or_skip(fig, out_path)

    # -- domain-mean Hovmoller: temperature and wind speed, layer vs time --
    domain_mean_temp = np.mean(temp_all, axis=(2, 3)) - 273.15
    wspd_all = np.sqrt(uwind_all**2 + vwind_all**2)
    domain_mean_wspd = np.mean(wspd_all, axis=(2, 3))

    for field, data, cmap, label in [
        ('temperature', domain_mean_temp, 'RdYlBu_r', 'Temperature (°C)'),
        ('windspeed', domain_mean_wspd, 'viridis', 'Wind speed (m/s)'),
    ]:
        fig, ax = plt.subplots(figsize=(12, 7))
        im = ax.pcolormesh(range(n_t), range(1, n_lay + 1), data.T, cmap=cmap, shading='auto')
        ax.invert_yaxis()
        plt.colorbar(im, ax=ax, label=f'Domain-mean {label}')
        ax.set_ylabel('CAMx layer (1 = surface)')
        ax.set_xticks(range(n_t))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
        ax.set_title(f'{DOMAIN} — {label} — layer vs time')
        plt.tight_layout()
        plt.savefig(f'{OUT_DIR}/wrfcamx_{DOMAIN}_3d_{field}_hovmoller.png', dpi=130, bbox_inches='tight')
        plt.close(fig)
        print(f'  Saved: {OUT_DIR}/wrfcamx_{DOMAIN}_3d_{field}_hovmoller.png')


# ── RUN ALL ───────────────────────────────────────────────────────────────────
print(f'Processing WRFCAMx output for {DOMAIN}...')
plot_lu_topo()
plot_2d_surface()
plot_kv_hovmoller()
plot_3d_fields()

print(f'New images: {new_images}, skipped (already existed): {skipped_images}')
print('Done.')
