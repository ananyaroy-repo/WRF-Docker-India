from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess, os

app = Flask(__name__)
CORS(app)

IMAGE     = "ananyahere/wrf-india:v2.1"
GEOG_PATH = "/home/ananya/WRF_PROJECTS/DATA/geog/WPS_GEOG_LOW_RES"
RUNS_BASE = "/home/ananya/WRF_PROJECTS/runs"

PRESET_DOMAINS = {
    "d01_27km":           {"nc_file": "geo_em.d01.nc"},
    "d02_9km_delhi":      {"nc_file": "geo_em_9km_delhi.nc"},
    "d03_3km_delhi_city": {"nc_file": "geo_em_3km_delhi_city.nc"},
    "d04_3km_mumbai":     {"nc_file": "geo_em_3km_mumbai.nc"},
}

def safe_domain(domain):
    return os.path.basename(domain.strip().replace(" ", "_"))

# ── HEALTH ───────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# ── RUN GEOGRID ───────────────────────────────────────────────────────────────
@app.route("/run-geogrid", methods=["POST"])
def run_geogrid():
    data     = request.json
    domain   = safe_domain(data.get("domain", ""))
    namelist = data.get("namelist", "")

    if not domain:
        return jsonify({"error": "No domain name provided"}), 400

    config_path = f"{RUNS_BASE}/{domain}"
    os.makedirs(config_path, exist_ok=True)

    with open(f"{config_path}/namelist.wps", "w") as f:
        f.write(namelist)

    nc_file = PRESET_DOMAINS.get(domain, {}).get("nc_file", "geo_em.d01.nc")

    cmd = (
        f"docker run --rm "
        f"-v {config_path}:/wrf/user-config "
        f"-v {config_path}:/wrf/output "
        f"-v {GEOG_PATH}:/wrf/WPS_GEOG "
        f"{IMAGE} bash -c \""
        f"cp /wrf/user-config/namelist.wps /wrf/WPS/namelist.wps && "
        f"cd /wrf/WPS && "
        f"./geogrid.exe 2>&1 && "
        f"cp geo_em.d01.nc /wrf/output/{nc_file} && "
        f"echo GEOGRID_DONE\""
    )

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=300
        )
        output = result.stdout + result.stderr

        # Strict success check — must see WPS completion message
        success = "Successful completion of geogrid" in output

        return jsonify({
            "output":     output,
            "success":    success,
            "returncode": result.returncode,
            "nc_file":    nc_file,
            "saved_to":   f"{config_path}/{nc_file}"
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out after 5 minutes"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── RUN VISUALIZATION ─────────────────────────────────────────────────────────
@app.route("/run-visualize", methods=["POST"])
def run_visualize():
    data   = request.json
    domain = safe_domain(data.get("domain", ""))

    if not domain:
        return jsonify({"error": "No domain specified"}), 400

    nc_file = PRESET_DOMAINS.get(domain, {}).get("nc_file", "geo_em.d01.nc")
    nc_path = f"{RUNS_BASE}/{domain}/{nc_file}"

    if not os.path.exists(nc_path):
        return jsonify({
            "error": f"geo_em file not found at {nc_path}. Run geogrid first."
        }), 400

    config_path = f"{RUNS_BASE}/{domain}"

    # Write a single-domain visualize script on the fly
    viz_script = f"""
import netCDF4 as nc
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import os

nc_path = '/wrf/user-config/{nc_file}'
out_dir = '/wrf/output'
os.makedirs(out_dir, exist_ok=True)

print(f"Processing: {{nc_path}}")
ds    = nc.Dataset(nc_path)
hgt   = ds.variables['HGT_M'][0, :, :]
xlat  = ds.variables['XLAT_M'][0, :, :]
xlong = ds.variables['XLONG_M'][0, :, :]
ds.close()

print(f"  Grid shape: {{hgt.shape}}")
print(f"  Elevation range: {{hgt.min():.1f}} — {{hgt.max():.1f}} m")

fig = plt.figure(figsize=(10, 8))
ax  = plt.axes(projection=ccrs.PlateCarree())
ax.add_feature(cfeature.COASTLINE.with_scale('10m'), linewidth=0.8)
ax.add_feature(cfeature.BORDERS.with_scale('10m'),   linewidth=0.5)
ax.add_feature(cfeature.STATES.with_scale('10m'),    linewidth=0.3, alpha=0.5)

im = ax.pcolormesh(xlong, xlat, hgt, cmap='terrain',
                   transform=ccrs.PlateCarree(), vmin=0)
plt.colorbar(im, ax=ax, label='Elevation (m)', shrink=0.8)
ax.set_title(f'Terrain Height — {domain}')
ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)

out_path = f'{{out_dir}}/terrain_{domain}.png'
plt.savefig(out_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"  Saved: {{out_path}}")
print("Done.")
"""

    # Write the script to the domain folder so it can be mounted
    script_path = f"{config_path}/viz_run.py"
    with open(script_path, "w") as f:
        f.write(viz_script)

    cmd = (
        f"docker run --rm "
        f"-v {config_path}:/wrf/user-config "
        f"-v {config_path}:/wrf/output "
        f"{IMAGE} python3 /wrf/user-config/viz_run.py 2>&1"
    )

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=300
        )
        output  = result.stdout + result.stderr
        success = result.returncode == 0 and "Done." in output

        # Only return PNGs from THIS domain folder
        png_files = []
        if os.path.exists(config_path):
            for f in sorted(os.listdir(config_path)):
                if f.startswith("terrain_") and f.endswith(".png"):
                    png_files.append(f"/image/{domain}/{f}")

        return jsonify({
            "output":    output,
            "success":   success,
            "png_files": png_files
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out after 5 minutes"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── SERVE PNG IMAGES ──────────────────────────────────────────────────────────
@app.route("/image/<domain>/<filename>")
def serve_image(domain, filename):
    if not filename.endswith(".png"):
        return "Not allowed", 403
    filepath = f"{RUNS_BASE}/{domain}/{filename}"
    if not os.path.exists(filepath):
        return "Not found", 404
    return send_file(filepath, mimetype="image/png")

if __name__ == "__main__":
    print("WRF Runner Server — http://localhost:5050")
    app.run(port=5050, debug=False)