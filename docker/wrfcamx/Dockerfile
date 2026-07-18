# ── WRF-CAMx extension of ananyahere/wrf-india:v2.1 ───────────────────────────
# Builds on the EXISTING WRF 4.7.1 + WPS image (ubuntu:resolute, GLIBC 2.43)
# rather than recompiling WRF/WPS from scratch — CAMx/WRFCAMx don't need a
# different WRF build, they just need CAMx + WRFCAMx + (optionally) TUV added.
#
# IMPORTANT — before building this image:
#   CAMx, WRFCAMx, and TUV all require accepting a license on camx.com to
#   download. They cannot be curl'd anonymously inside this Dockerfile.
#   Download them yourself and place them in ./docker/vendor/ next to this
#   Dockerfile, named exactly:
#     docker/vendor/CAMx_v7.32.src.tgz
#     docker/vendor/wrfcamx_v5.2.10Jan22.tgz
#     docker/vendor/tuv4.8.tgz        (optional — photolysis rates; skip if unused)
#
# THIS IS A DRAFT, NOT A VERIFIED-WORKING BUILD.
# The compile fixes below are adapted from a working reference image found on
# `sustain` (wrfcamx-pipeline:latest / :hotfix), which was built on ubuntu:22.04
# with an older gfortran than this image's ubuntu:resolute. Newer gfortran
# versions are typically STRICTER about legacy Fortran, not more lenient — so
# these flags may need to be extended, not removed, if the build fails. Expect
# at least one real fix-and-rebuild cycle, same as the original WRF/WPS build.

FROM ananyahere/wrf-india:v2.1

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /opt

# Confirm the build toolchain used for WRF/WPS is still present.
# (Should already be true since this image compiled WRF/WPS itself — this is
#  a cheap safety net, not expected to install anything new.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gfortran make csh \
    && rm -rf /var/lib/apt/lists/*

# ── CAMx v7.32 ──────────────────────────────────────────────────────────────
COPY docker/vendor/CAMx_v7.32.src.tgz /tmp/vendor/
RUN mkdir -p /opt/camx && tar xzf /tmp/vendor/CAMx_v7.32.src.tgz -C /opt/camx --strip-components=1 \
    && cd /opt/camx \
    # Known gfortran-strictness fixes (from the reference build):
    && sed -i 's|-fno-align-commons|-fno-align-commons -fallow-argument-mismatch -fallow-invalid-boz|' Makefile \
    # Known source bug: unbalanced parentheses in pnt_update.f
    && sed -i 's|abs(hstk(n) .LT. 0.01 .OR.|abs(hstk(n)) .LT. 0.01 .OR.|; s|0.01 ) ) then|0.01 ) then|' CAMx/pnt_update.f \
    && { make COMPILER=gfortranomp MPI=false NCF=NCF4_C NCF_INST=/usr > make.log 2>&1 || true; } \
    && BIN=$(ls CAMx.v7.32.* 2>/dev/null | head -1) \
    && { [ -n "$BIN" ] || { echo "==== CAMx BUILD FAILED ===="; grep -iE "error" make.log | tail -40; exit 1; }; } \
    && ln -sf "$BIN" CAMx.v7.32 && ls -l CAMx.v7.32

# ── WRFCAMx v5.2 (+ TUV 4.8, optional) ───────────────────────────────────────
COPY docker/vendor/wrfcamx_v5.2.10Jan22.tgz /tmp/vendor/
COPY docker/vendor/tuv4.8*.tgz /tmp/vendor/
RUN mkdir -p /opt/camx/preproc && cd /opt/camx/preproc \
    && tar xzf /tmp/vendor/wrfcamx_v5.2*.tgz \
    && cd wrfcamx*/src \
    # Point the Makefile at this image's compiler and existing netCDF install
    # (same -lnetcdff fix pattern already used for your own WPS build).
    && sed -i '1s|.*|FC = gfortran|; 2s|.*|FLGS = -O2 -fno-align-commons -frecord-marker=4 -ffixed-line-length-0 -fallow-argument-mismatch -fallow-invalid-boz -std=legacy|' Makefile \
    && sed -i 's|-L/usr/local/netcdf/lib|-L/usr/lib/x86_64-linux-gnu|; s|-I/usr/local/netcdf/include|-I/usr/include|' Makefile \
    && { make > make.log 2>&1 || true; } \
    && { test -f wrfcamx || { echo "==== WRFCAMX BUILD FAILED ===="; tail -40 make.log; exit 1; }; }

RUN if ls /tmp/vendor/tuv4.8*.tgz >/dev/null 2>&1; then \
      cd /opt/camx/preproc && tar xzf /tmp/vendor/tuv4.8*.tgz \
      && cd tuv4.8*/src \
      && sed -i 's|^FFLAGS = -O2 -Mextend -Kieee|FFLAGS = -O2 -frecord-marker=4 -ffixed-line-length-0 -fallow-argument-mismatch -fallow-invalid-boz -std=legacy|; s|^FC = pgf90|FC = gfortran|' Makefile \
      && { make > make.log 2>&1 || true; } \
      && { test -f tuv || { echo "==== TUV BUILD FAILED ===="; tail -40 make.log; exit 1; }; } \
    ; fi

WORKDIR /wrf
CMD ["bash"]
