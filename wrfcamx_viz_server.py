from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess, os, glob

app = Flask(__name__)
CORS(app)

IMAGE          = "ananyahere/wrf-india:v2.2"
BASE_DIR       = "/mnt/nas/gfs_data/wrf_setup"
DEFAULT_OUTPUT = "/mnt/nas/gfs_data/wrf_setup/viz_output_wrfcamx"
VIZ_SCRIPT     = os.path.expanduser("~/WRF_PROJECTS/wrfcamx_build/visualize_wrfcamx.py")
CARTOPY_CACHE  = os.path.expanduser("~/wrf_work/cartopy_cache")
DOMAINS        = ["d01", "d02", "d03", "d04"]

def safe_path(path):
    if not path or not path.strip():
        return None
    return os.path.abspath(os.path.expanduser(path.strip()))

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/wrfcamx-status", methods=["POST"])
def wrfcamx_status():
    file_status = {}
    for d in DOMAINS:
        domain_dir = f"{BASE_DIR}/camx_input_{d}"
        file_status[d] = {
            "lu":   os.path.exists(f"{domain_dir}/camx.lu.{d}.nc"),
            "2d":   os.path.exists(f"{domain_dir}/camx.2d.{d}.nc"),
            "3d":   os.path.exists(f"{domain_dir}/camx.3d.{d}.nc"),
            "kv":   os.path.exists(f"{domain_dir}/camx.kv.{d}.nc.YSU"),
        }
    return jsonify({"file_status": file_status})

@app.route("/run-visualize-wrfcamx", methods=["POST"])
def run_visualize_wrfcamx():
    data       = request.json or {}
    domain     = data.get("domain", "d01")
    output_dir = safe_path(data.get("output_dir", "")) or DEFAULT_OUTPUT

    if domain not in DOMAINS:
        return jsonify({"error": f"Unknown domain '{domain}'"}), 400

    domain_dir = f"{BASE_DIR}/camx_input_{domain}"
    if not os.path.isdir(domain_dir):
        return jsonify({"error": f"WRFCAMx output directory not found: {domain_dir}"}), 400
    if not os.path.isfile(VIZ_SCRIPT):
        return jsonify({"error": f"Visualization script not found: {VIZ_SCRIPT}"}), 400

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(CARTOPY_CACHE, exist_ok=True)

    cmd = (
        f"docker run --rm "
        f"-v /mnt/nas:/data "
        f"-v {output_dir}:/output "
        f"-v {VIZ_SCRIPT}:/viz.py "
        f"-v {CARTOPY_CACHE}:/root/.local/share/cartopy "
        f"-e CARTOPY_DATA_DIR=/root/.local/share/cartopy "
        f"{IMAGE} python3 /viz.py {domain}"
    )

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1200)
        output  = result.stdout + result.stderr
        success = "Done." in output

        patterns = [
            f"wrfcamx_{domain}_lu_topo.png",
            f"wrfcamx_{domain}_pbl_comparison.png",
            f"wrfcamx_{domain}_kv_hovmoller.png",
            f"wrfcamx_{domain}_3d_temperature_hovmoller.png",
            f"wrfcamx_{domain}_3d_windspeed_hovmoller.png",
        ]
        summary_images = []
        for p in patterns:
            full = f"{output_dir}/{p}"
            if os.path.exists(full):
                encoded = output_dir.replace("/", "__SLASH__")
                summary_images.append(f"/image/{encoded}/{p}")

        timeseries_2d = sorted(glob.glob(f"{output_dir}/wrfcamx_{domain}_2d_*.png"))
        timeseries_3d = sorted(glob.glob(f"{output_dir}/wrfcamx_{domain}_3dsfc_*.png"))
        encoded = output_dir.replace("/", "__SLASH__")
        ts_2d_urls = [f"/image/{encoded}/{os.path.basename(f)}" for f in timeseries_2d]
        ts_3d_urls = [f"/image/{encoded}/{os.path.basename(f)}" for f in timeseries_3d]

        return jsonify({
            "output": output,
            "success": success,
            "summary_images": summary_images,
            "timeseries_2d": ts_2d_urls,
            "timeseries_3dsfc": ts_3d_urls,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out after 20 minutes"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/image/<encoded_path>/<filename>")
def serve_image(encoded_path, filename):
    if not filename.endswith(".png"):
        return "Not allowed", 403
    real_path = encoded_path.replace("__SLASH__", "/")
    filepath  = f"{real_path}/{filename}"
    if not os.path.exists(filepath):
        return f"Not found: {filepath}", 404
    return send_file(filepath, mimetype="image/png")

if __name__ == "__main__":
    print("WRFCAMx Viz Server — http://localhost:5052")
    print(f"Base dir: {BASE_DIR}")
    print(f"Default output dir: {DEFAULT_OUTPUT}")
    app.run(port=5052, debug=False, host="0.0.0.0", threaded=True)
