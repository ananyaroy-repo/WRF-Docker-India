from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess, os

app = Flask(__name__)
CORS(app)

IMAGE = "ananyahere/wrf-india:v2.1"

PRESET_DOMAINS = {
    "d01_27km":           {"nc_file": "geo_em.d01.nc"},
    "d02_9km_delhi":      {"nc_file": "geo_em_9km_delhi.nc"},
    "d03_3km_delhi_city": {"nc_file": "geo_em_3km_delhi_city.nc"},
    "d04_3km_mumbai":     {"nc_file": "geo_em_3km_mumbai.nc"},
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

    nc_file = PRESET_DOMAINS.get(domain, {}).get("nc_file", "geo_em.d01.nc")

    cmd = (
        f"docker run --rm "
        f"-v {output_path}:/wrf/user-config "
        f"-v {output_path}:/wrf/output "
        f"-v {geog_path}:/wrf/WPS_GEOG "
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
        output  = result.stdout + result.stderr
        success = "Successful completion of geogrid" in output
        return jsonify({
            "output":      output,
            "success":     success,
            "returncode":  result.returncode,
            "nc_file":     nc_file,
            "saved_to":    f"{output_path}/{nc_file}"
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

    nc_file = PRESET_DOMAINS.get(domain, {}).get("nc_file", "geo_em.d01.nc")
    nc_path = f"{output_path}/{nc_file}"

    if not os.path.exists(nc_path):
        return jsonify({
            "error": f"geo_em file not found at {nc_path}. Run geogrid first."
        }), 400

    # Write a domain-specific viz script into the output folder
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
ax.set_title('Terrain Height — {domain}')
gl = ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)
gl.right_labels = False

out_path = f'{{out_dir}}/terrain_{domain}.png'
plt.savefig(out_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"  Saved: {{out_path}}")
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
            cmd, shell=True, capture_output=True, text=True, timeout=300
        )
        out     = result.stdout + result.stderr
        success = result.returncode == 0 and "Done." in out

        png_files = []
        expected  = f"terrain_{domain}.png"
        if os.path.exists(f"{output_path}/{expected}"):
            # Pass full output_path encoded in the URL so serve_image can find it
            encoded = output_path.replace("/", "__SLASH__")
            png_files.append(f"/image/{encoded}/{expected}")

        return jsonify({
            "output":    out,
            "success":   success,
            "png_files": png_files
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out after 5 minutes"}), 408
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