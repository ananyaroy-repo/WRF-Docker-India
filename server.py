from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess, os, glob, re

app = Flask(__name__)
CORS(app)

IMAGE = "ananyahere/wrf-india:v2.1"

PRESET_DOMAINS = {
    "d01_27km":              {"nc_file": "geo_em.d01.nc"},
    "d02_9km_delhi":         {"nc_file": "geo_em_9km_delhi.nc"},
    "d03_9km_south_india":   {"nc_file": "geo_em_9km_south_india.nc"},
    "d04_9km_wb_odisha":     {"nc_file": "geo_em_9km_wb_odisha.nc"},
}

def safe_path(path):
    """Expand ~, resolve to absolute path. Reject empty strings."""
    if not path or not path.strip():
        return None
    return os.path.abspath(os.path.expanduser(path.strip()))

def safe_domain(domain):
    return os.path.basename(domain.strip().replace(" ", "_"))

# ── HEALTH ────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# ── RUN GEOGRID ───────────────────────────────────────────────────────────────
@app.route("/run-geogrid", methods=["POST"])
def run_geogrid():
    data        = request.json
    domain      = safe_domain(data.get("domain", ""))
    namelist    = data.get("namelist", "")
    geog_path   = safe_path(data.get("geog_path", ""))
    output_path = safe_path(data.get("output_path", ""))

    if not domain:
        return jsonify({"error": "No domain name provided"}), 400
    if not geog_path:
        return jsonify({"error": "No WPS_GEOG path provided"}), 400
    if not output_path:
        return jsonify({"error": "No output folder path provided"}), 400
    if not os.path.isdir(geog_path):
        return jsonify({"error": f"WPS_GEOG folder not found: {geog_path}"}), 400

    os.makedirs(output_path, exist_ok=True)

    # Write namelist.wps to the output folder
    with open(f"{output_path}/namelist.wps", "w") as f:
        f.write(namelist)

    # Clean up any geo_em files from a PREVIOUS run in this folder first,
    # so visualize() doesn't pick up stale files from an earlier single/nested config.
    for stale in glob.glob(f"{output_path}/geo_em.d*.nc"):
        try:
            os.remove(stale)
        except OSError:
            pass

    cmd = (
        f"docker run --rm "
        f"-v {output_path}:/wrf/user-config "
        f"-v {output_path}:/wrf/output "
        f"-v {geog_path}:/wrf/WPS_GEOG "
        f"{IMAGE} bash -c \""
        f"cp /wrf/user-config/namelist.wps /wrf/WPS/namelist.wps && "
        f"cd /wrf/WPS && "
        f"./geogrid.exe 2>&1 && "
        f"cp geo_em.d*.nc /wrf/output/ && "
        f"echo GEOGRID_DONE\""
    )

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=300
        )
        output  = result.stdout + result.stderr
        success = "Successful completion of geogrid" in output

        # Report which domain files actually landed on disk
        produced = sorted(os.path.basename(p) for p in glob.glob(f"{output_path}/geo_em.d*.nc"))

        return jsonify({
            "output":      output,
            "success":     success,
            "returncode":  result.returncode,
            "domains_found": produced,
            "saved_to":    output_path
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out after 5 minutes"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── RUN VISUALIZATION ─────────────────────────────────────────────────────────
@app.route("/run-visualize", methods=["POST"])
def run_visualize():
    data        = request.json
    domain      = safe_domain(data.get("domain", ""))
    output_path = safe_path(data.get("output_path", ""))

    if not domain:
        return jsonify({"error": "No domain specified"}), 400
    if not output_path:
        return jsonify({"error": "No output folder path provided"}), 400

    # ── Discover whichever geo_em.d*.nc files actually exist in this run ──
    # This makes single-domain AND nested-domain runs both work automatically:
    # - single domain run  -> exactly one geo_em.d01.nc found
    # - nested domain run  -> geo_em.d01.nc, geo_em.d02.nc, geo_em.d03.nc... all found
    found_files = sorted(glob.glob(f"{output_path}/geo_em.d*.nc"))

    if not found_files:
        return jsonify({
            "error": f"No geo_em.d*.nc files found in {output_path}. Run geogrid first."
        }), 400

    # Build a script that loops over every domain file found and plots each one
    domain_list_py = repr([os.path.basename(p) for p in found_files])

    viz_script = f"""
import netCDF4 as nc
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import os, re

out_dir = '/wrf/output'
os.makedirs(out_dir, exist_ok=True)

domain_files = {domain_list_py}

for nc_filename in domain_files:
    nc_path = f'/wrf/user-config/{{nc_filename}}'
    # Extract dNN label from filename, e.g. geo_em.d02.nc -> d02
    m = re.search(r'(d\\d{{2}})', nc_filename)
    dlabel = m.group(1) if m else nc_filename.replace('.nc', '')

    print(f"Processing: {{nc_path}}")
    try:
        ds    = nc.Dataset(nc_path)
        HGT   = ds.variables['HGT_M'][0, :, :]
        XLAT  = ds.variables['XLAT_M'][0, :, :]
        XLONG = ds.variables['XLONG_M'][0, :, :]
        ds.close()

        print(f"  Grid shape: {{HGT.shape}}")
        print(f"  Elevation range: {{HGT.min():.1f}} — {{HGT.max():.1f}} m")

        fig, ax = plt.subplots(figsize=(10, 7),
                               subplot_kw={{'projection': ccrs.PlateCarree()}})
        cf = ax.contourf(XLONG, XLAT, HGT,
                         levels=30, cmap='terrain',
                         transform=ccrs.PlateCarree())
        plt.colorbar(cf, ax=ax, label='Elevation (m)')
        ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
        ax.add_feature(cfeature.BORDERS,   linewidth=0.5, linestyle='--')
        ax.add_feature(cfeature.STATES,    linewidth=0.3, linestyle=':')
        ax.set_title(f'Terrain Height — {domain} ({{dlabel}})')
        gl = ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)
        gl.right_labels = False

        out_path = f'{{out_dir}}/terrain_{domain}_{{dlabel}}.png'
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved: {{out_path}}")
    except Exception as e:
        print(f"  ERROR processing {{nc_filename}}: {{e}}")

print("Done.")
"""

    script_path = f"{output_path}/viz_run.py"
    with open(script_path, "w") as f:
        f.write(viz_script)

    cmd = (
        f"docker run --rm "
        f"-v {output_path}:/wrf/user-config "
        f"-v {output_path}:/wrf/output "
        f"{IMAGE} python3 /wrf/user-config/viz_run.py 2>&1"
    )

    try:
        result  = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=600
        )
        out     = result.stdout + result.stderr
        success = result.returncode == 0 and "Done." in out

        # Collect every terrain_<domain>_dNN.png produced for THIS run
        png_files = []
        pattern = f"{output_path}/terrain_{domain}_d*.png"
        for png_path in sorted(glob.glob(pattern)):
            filename = os.path.basename(png_path)
            encoded  = output_path.replace("/", "__SLASH__")
            png_files.append(f"/image/{encoded}/{filename}")

        return jsonify({
            "output":    out,
            "success":   success,
            "png_files": png_files,
            "domains_processed": [os.path.basename(p) for p in found_files]
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out after 10 minutes"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── SERVE PNG IMAGES ──────────────────────────────────────────────────────────
@app.route("/image/<encoded_path>/<filename>")
def serve_image(encoded_path, filename):
    if not filename.endswith(".png"):
        return "Not allowed", 403
    # Decode the path back from __SLASH__ encoding
    real_path = encoded_path.replace("__SLASH__", "/")
    filepath  = f"{real_path}/{filename}"
    if not os.path.exists(filepath):
        return f"Not found: {filepath}", 404
    return send_file(filepath, mimetype="image/png")

if __name__ == "__main__":
    print("WRF Runner Server — http://localhost:5050")
    app.run(port=5050, debug=False)