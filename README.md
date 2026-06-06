# WRF India Downscaling - Setup & Dockerization
### SRIP 2026 Internship Progress Report
**By:** Ananya | **Docker Hub:** [ananyahere/wrf-india](https://hub.docker.com/r/ananyahere/wrf-india)

---

## Overview
This document describes the setup, compilation, and containerization of the **Weather Research and Forecasting (WRF)** model for high-resolution atmospheric downscaling over India. This work is part of a larger project to develop AI-based downscaling models (inspired by Aurora, ClimaX, GraphCast) for Indian weather domains. It isa basic preliminary WRF model run for India and it's specific regions.

---

## System Setup
- **OS:** Ubuntu 26.04 LTS (WSL2 on Windows)
- **Kernel:** 6.6.114.1-microsoft-standard-WSL2
- **RAM:** 8GB
- **Storage:** 1TB (Linux filesystem)
- **Docker:** v29.4.2

---
## Image Versions
| Tag | Size | Description |
|-----|------|-------------|
| v1 | 4.37 GB | WRF + WPS + 4 India domain configs + geog data (bundled) |
| v2 | 2.62 GB | WRF + WPS + dependencies only (configs user-mounted) |
| v2.1 | 3.33 GB | v2 + Python visualization support (netCDF4, matplotlib, cartopy) |

## Step 1: WRF Compilation (Completed)

### Dependencies Installed
```bash
sudo apt-get install -y gcc gfortran g++ make \
    libnetcdf-dev libnetcdff-dev libpng-dev \
    zlib1g-dev openmpi-bin libopenmpi-dev netcdf-bin
```

### Environment Variables (~/.bashrc)
```bash
export NETCDF=/usr
export HDF5=/usr/lib/x86_64-linux-gnu/hdf5/serial
export JASPERLIB=/usr/lib/x86_64-linux-gnu
export JASPERINC=/usr/include
export WRF_DIR=$HOME/WRF_PROJECTS/WRF
export PATH=$PATH:/usr/lib/openmpi/bin
```

### WRF Build Steps
```bash
cd ~/WRF_PROJECTS/WRF
./configure        # Selected option 34 (dmpar, gfortran)
./compile em_real >& compile.log &
```

### Result
```
 WRF compiled successfully
wrf.exe    ← main simulation executable
real.exe   ← data preprocessing executable
ndown.exe  ← nesting executable
tc.exe     ← tropical cyclone executable
```

---

## Step 2: WPS Compilation (Partially completed till geogrid due to space constraints)

WPS (WRF Preprocessing System) processes geographical and meteorological data before running WRF.

### Key Fix Applied
Added `-lnetcdff` to `configure.wps` to link Fortran NetCDF library:
```
WRF_LIB = ... -lnetcdf -lnetcdff
```

Removed jasper (JPEG2000) dependency - not available in Ubuntu 26.04:
```
COMPRESSION_LIBS = -lpng -lz
FDEFS            = -DUSE_PNG
```

### WPS Build Steps
```bash
cd ~/WPS
./configure       # Selected option 3 (dmpar)
./compile >& compile.log &
```

### Result
```bash
$ ls ~/WPS/geogrid.exe ~/WPS/ungrib.exe ~/WPS/metgrid.exe
/home/ananya/WPS/geogrid.exe
/home/ananya/WPS/metgrid.exe  
/home/ananya/WPS/ungrib.exe
```
```
 geogrid.exe  - processes geographical/terrain data    
 ungrib.exe   - unpacks GRIB meteorological data
 metgrid.exe  - interpolates met data to WRF grid
```

###  Note on WPS Pipeline
```
Due to local RAM constraints (8GB), only **geogrid.exe** was run locally.
- `geogrid.exe`  — completed successfully for all 4 domains
- `ungrib.exe`  — requires GFS/ERA5 meteorological data (~500MB per 6hrs)
- `metgrid.exe`  — requires ungrib output

Full WPS pipeline (ungrib → metgrid) and WRF simulation (real.exe → wrf.exe) 
will be completed once department HPC access is available.
```

---

## Step 3: Domain Configurations (Completed)

Four domain configurations were tested representing different resolutions over India:

| Domain | Resolution | Region | Center Lat | Center Lon | Grid Size |
|--------|-----------|--------|-----------|-----------|-----------|
| d01 | 27 km | All India | 20.0°N | 78.0°E | 50×50 |
| d02 | 9 km | Delhi Region | 28.6°N | 77.2°E | 60×60 |
| d03 | 3 km | Delhi City | 28.6°N | 77.2°E | 60×60 |
| d04 | 3 km | Mumbai | 19.0°N | 72.8°E | 60×60 |

### Geographic Data Downloaded
```bash
wget https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_low_res_mandatory.tar.gz
# Size: ~143MB (low resolution mandatory fields)
```

### geogrid.exe Run for Each Domain
```bash
cd ~/WPS
./geogrid.exe >& geogrid.log
tail geogrid.log
```

### Success Output (same for all 4 domains)
```
*** Successful completion of program geogrid.exe ***
```

### Domain Files Saved
```bash
$ ls ~/WRF_PROJECTS/runs/
d01_27km   d02_9km_delhi   d03_3km_delhi_city   d04_3km_mumbai
```

Each folder contains:
- `geo_em_*.nc` — terrain/land-use NetCDF file for that domain
- `namelist.wps` — configuration used for that domain

---

## Step 4: Docker Containerization (Completed)

### Dockerfile
```dockerfile
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    gcc gfortran g++ make wget curl git csh m4 perl \
    libnetcdf-dev libnetcdff-dev libpng-dev zlib1g-dev \
    openmpi-bin libopenmpi-dev netcdf-bin \
    && apt-get clean

ENV NETCDF=/usr
ENV HDF5=/usr/lib/x86_64-linux-gnu/hdf5/serial
ENV PATH=$PATH:/usr/lib/openmpi/bin
ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu
ENV WRF_DIR=/wrf/WRF

RUN mkdir -p /wrf/WPS_GEOG
WORKDIR /wrf

COPY WRF/ /wrf/WRF/
COPY WPS/ /wrf/WPS/

ENV PATH=$PATH:/wrf/WRF/main:/wrf/WPS
CMD ["/bin/bash"]
```

### Build Command
```bash
docker build -t ananyahere/wrf-india:v2 .
```

### Build Result
```
[14/14] FINISHED
Successfully built and tagged ananyahere/wrf-india:v2
Image size: 2.62GB (dependencies only, no configs)
```

### Verified Contents Inside Container
```bash
$ docker run -it ananyahere/wrf-india:v2 /bin/bash
root@container:/wrf# ls /wrf/
WPS  WPS_GEOG  WRF

root@container:/wrf# ls /wrf/WRF/main/wrf.exe
/wrf/WRF/main/wrf.exe  

root@container:/wrf# ls /wrf/WPS/geogrid.exe
/wrf/WPS/geogrid.exe    
```

### Pushed to Docker Hub
```bash
docker push ananyahere/wrf-india:v2
```
```
v2: digest: sha256:43284639079fb5d6c3030faf8c34431ca0a7fe2d9257a03ac357825eca96ee1d
Available at: https://hub.docker.com/r/ananyahere/wrf-india
```

### How to Use This Container

**Pull the image (v2 - dependencies only):**
```bash
docker pull ananyahere/wrf-india:v2
```

**Run with your own configs:**
```bash
docker run -it \
  -v /path/to/namelist.wps:/wrf/WPS/namelist.wps \
  -v /path/to/namelist.input:/wrf/WRF/namelist.input \
  -v /path/to/WPS_GEOG:/wrf/WPS_GEOG \
  ananyahere/wrf-india:v2
```
**For visualization support (recommended):**
```bash
docker pull ananyahere/wrf-india:v2.1
```

## Step 5: Docker Image v2.1 — Visualization Support Added

Building on v2, image v2.1 adds Python-based terrain visualization capabilities directly inside the container.

### What's New in v2.1
- Python 3, pip, netCDF4, matplotlib, numpy, cartopy installed inside the image
- `visualize.py` script included at `/wrf/visualize.py`
- Reads `geo_em.d01.nc` (geogrid output) and produces a terrain elevation map

### Updated Dockerfile (v2.1)
```dockerfile
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    gcc gfortran g++ make wget curl git csh m4 perl \
    pkg-config python3-dev \
    libnetcdf-dev libnetcdff-dev libpng-dev zlib1g-dev \
    openmpi-bin libopenmpi-dev netcdf-bin \
    python3 python3-pip \
    libgeos-dev libproj-dev proj-bin \
    && apt-get clean

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install netCDF4 matplotlib numpy cartopy

ENV NETCDF=/usr
ENV HDF5=/usr/lib/x86_64-linux-gnu/hdf5/serial
ENV PATH=$PATH:/usr/lib/openmpi/bin
ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu
ENV WRF_DIR=/wrf/WRF

RUN mkdir -p /wrf/WPS_GEOG
WORKDIR /wrf

COPY WRF/ /wrf/WRF/
COPY WPS/ /wrf/WPS/
COPY visualize_terrain_all4.py /wrf/visualize.py

ENV PATH=$PATH:/wrf/WRF/main:/wrf/WPS
CMD ["/bin/bash"]
```

### Build Command
```bash
docker build -t ananyahere/wrf-india:v2.1 .
```

### How to Run Visualization
```bash
docker run -it \
  -v /path/to/your/runs/d01_27km:/wrf/user-config \
  -v /path/to/your/output:/wrf/output \
  ananyahere/wrf-india:v2.1 bash
```
Inside the container:
```bash
python3 /wrf/visualize.py
```
Output: terrain elevation plot saved to `/wrf/output/` on your host machine.

**Sample configs available in `/configs` folder of this repo.**

---

## Current Status

| Task | Status |
|------|--------|
| WRF Compilation |  Complete |
| WPS Compilation |  Complete |
| Geographic Data Download |  Complete |
| Domain Config - d01 (27km All India) |  Complete |
| Domain Config - d02 (9km Delhi) |  Complete |
| Domain Config - d03 (3km Delhi City) |  Complete |
| Domain Config - d04 (3km Mumbai) |  Complete |
| Docker Image v2.1 Built (+ Python visualization) | Complete |
| Docker Image v2.1 Pushed to Hub | Complete |
| Docker Container Built |  Complete |
| Docker Container Pushed to Hub |  Complete |
| GFS Data Download & ungrib |  Pending HPC Access |
| metgrid |  Pending HPC Access |
| Full WRF Simulation Run |  Pending HPC Access |
| AI Downscaling Model |  Upcoming |


---

## Web UI — Domain Config Generator

A simple browser-based UI to generate `namelist.wps` files and get the exact Docker run command for your domain.

**Open:** [`wrf_runner_ui.html`](./wrf_runner_ui.html) in any browser — no server needed.

**Features:**
- Load example India domain presets (All India 27km, Delhi 9km, Delhi 3km, Mumbai 3km)
- Enter any custom lat/lon, resolution, grid size, date, and time
- Generates `namelist.wps` automatically
- Shows the exact `docker run` command with volume mounts
- All fields are editable — not locked to India configs

**How to use:**
1. Download or clone this repo
2. Open `wrf_runner_ui.html` in your browser
3. Fill in your domain settings
4. Click Generate — copy the Docker command shown

---

## References
- [WRF Users Guide](https://www2.mmm.ucar.edu/wrf/users/)
- [WPS Documentation](https://www2.mmm.ucar.edu/wrf/users/docs/user_guide_v4/v4.0/users_guide_chap3.html)
- [Docker Hub - ananyahere/wrf-india](https://hub.docker.com/r/ananyahere/wrf-india)

