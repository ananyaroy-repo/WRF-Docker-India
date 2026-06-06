# WRF Docker Container
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    gfortran \
    g++ \
    make \
    wget \
    curl \
    git \
    csh \
    m4 \
    perl \
    pkg-config \
    python3-dev \
    libnetcdf-dev \
    libnetcdff-dev \
    libpng-dev \
    zlib1g-dev \
    openmpi-bin \
    libopenmpi-dev \
    netcdf-bin \
    python3 \
    python3-pip \
    libgeos-dev \
    libproj-dev \
    proj-bin \
    && apt-get clean

# Upgrade pip first, then install Python libraries
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install netCDF4 matplotlib numpy cartopy

# Set environment variables
ENV NETCDF=/usr
ENV HDF5=/usr/lib/x86_64-linux-gnu/hdf5/serial
ENV PATH=$PATH:/usr/lib/openmpi/bin
ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu
ENV WRF_DIR=/wrf/WRF

# Create directories
RUN mkdir -p /wrf/WPS_GEOG
WORKDIR /wrf

# Copy compiled WRF and WPS
COPY WRF/ /wrf/WRF/
COPY WPS/ /wrf/WPS/

# Copy visualization script
COPY visualize_terrain_all4.py /wrf/visualize.py

ENV PATH=$PATH:/wrf/WRF/main:/wrf/WPS
CMD ["/bin/bash"]
