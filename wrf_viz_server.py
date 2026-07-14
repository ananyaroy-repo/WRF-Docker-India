from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess, os, glob

app = Flask(__name__)
CORS(app)

IMAGE          = "ananyahere/wrf-india:v2.1"
DEFAULT_RUN    = "/mnt/nas/gfs_data/wrf_setup/real_wrf_run_july2023_FINAL"
DEFAULT_OUTPUT = "/mnt/nas/gfs_data/wrf_setup/viz_output_final"
VIZ_SCRIPT     = os.path.expanduser("~/wrf_work/viz/visualize_wrf_timeseries.py")
CARTOPY_CACHE  = os.path.expanduser("~/wrf_work/cartopy_cache")
DOMAINS        = ["d01", "d02", "d03", "d04"]

def safe_path(path):
    if not path or not path.strip():
        return None
    return os.path.abspath(os.path.expanduser(path.strip()))

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/wrf-status", methods=["POST"])
def wrf_status():
    data    = request.json or {}
    run_dir = safe_path(data.get("run_dir", "")) or DEFAULT_RUN

    try:
        ps_out = subprocess.run(
            "ps aux | grep -c '[w]rf.exe'", shell=True,
            capture_output=True, text=True
        )
        proc_count = int(ps_out.stdout.strip() or "0")
    except Exception:
        proc_count = -1

    file_counts = {}
    for d in DOMAINS:
        file_counts[d] = len(glob.glob(f"{run_dir}/wrfout_{d}_*"))

    return jsonify({
        "process_count": proc_count,
        "running": proc_count > 0,
        "file_counts": file_counts,
        "last_log_lines": [],
        "run_dir": run_dir
    })

@app.route("/run-visualize-wrf", methods=["POST"])
def run_visualize_wrf():
    data       = request.json or {}
    domain     = data.get("domain", "d01")
    run_dir    = safe_path(data.get("run_dir", "")) or DEFAULT_RUN
    output_dir = safe_path(data.get("output_dir", "")) or DEFAULT_OUTPUT

    if domain not in DOMAINS:
        return jsonify({"error": f"Unknown domain '{domain}'"}), 400
    if not os.path.isdir(run_dir):
        return jsonify({"error": f"Run directory not found: {run_dir}"}), 400
    if not os.path.isfile(VIZ_SCRIPT):
        return jsonify({"error": f"Visualization script not found: {VIZ_SCRIPT}"}), 400

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(CARTOPY_CACHE, exist_ok=True)

    cmd = (
        f"docker run --rm "
        f"-v {run_dir}:/data "
        f"-v /mnt/nas:/mnt/nas "
        f"-v {output_dir}:/output "
        f"-v {VIZ_SCRIPT}:/viz.py "
        f"-v {CARTOPY_CACHE}:/root/.local/share/cartopy "
        f"-e CARTOPY_DATA_DIR=/root/.local/share/cartopy "
        f"{IMAGE} python3 /viz.py {domain}"
    )

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=900)
        output  = result.stdout + result.stderr
        success = "Done." in output

        pattern = f"{output_dir}/wrf_met_{domain}_*.png"
        png_files = []
        for png_path in sorted(glob.glob(pattern)):
            filename = os.path.basename(png_path)
            encoded  = output_dir.replace("/", "__SLASH__")
            png_files.append(f"/image/{encoded}/{filename}")

        summary_path = f"{output_dir}/wrf_timeseries_summary_{domain}.png"
        summary_url = None
        if os.path.exists(summary_path):
            encoded = output_dir.replace("/", "__SLASH__")
            summary_url = f"/image/{encoded}/wrf_timeseries_summary_{domain}.png"

        return jsonify({
            "output": output,
            "success": success,
            "png_files": png_files,
            "summary_url": summary_url
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out after 15 minutes"}), 408
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
    print("WRF Viz Server (for the HPC server) — http://localhost:5051")
    print(f"Default run dir:    {DEFAULT_RUN}")
    print(f"Default output dir: {DEFAULT_OUTPUT}")
    app.run(port=5051, debug=False, host="0.0.0.0", threaded=True)
