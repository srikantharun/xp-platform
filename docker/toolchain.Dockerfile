# syntax=docker/dockerfile:1.7
# docker/toolchain.Dockerfile — THE build environment for xp-pricer: CI jobs, the devcontainer
# and local builds all use this image. AlmaLinux 8 = RHEL 8 userland, so binaries built here
# need nothing newer than glibc 2.28 (docs/toolchain.md). Every tool is pinned by version and,
# for downloads, by SHA-256.
#
#   docker build -f docker/toolchain.Dockerfile -t xp-toolchain:dev .
#   tools/ci/check_toolchain_image.sh     # build inside it, glibc floor, cache hits
FROM almalinux:8@sha256:2d0f2eb2a83cc09dbc2eb92fade4dbe8f709628149e81aa00aec70630406603b

# ---- pins (bump in one MR, rebuild, re-run tools/ci/check_toolchain_image.sh) ----
ARG GCC_TOOLSET=13
ARG CLANG_NEVR=17.0.6-1.module_el8.10.0+3757+fc27b834
ARG LLVM_LIBS_NEVR=17.0.6-2.module_el8.10.0+3757+fc27b834
ARG CMAKE_VERSION=3.28.6
ARG CMAKE_SHA256=931e3c0d546ee03ca72bb147ccd9b49e3b6252f765f66bf21b9d165519940458
ARG NINJA_VERSION=1.12.1
# ninja publishes no checksum file; hash recorded from the official release asset.
ARG NINJA_SHA256=6f98805688d19672bd699fbbfa2c2cf0fc054ac3df1f0e6a47664d963d530255
ARG SCCACHE_VERSION=v0.19.0
ARG SCCACHE_SHA256=aa73c7270c997894038c0d8f0d297865f57569e1687883322bc431713d4bb9dd
ARG UV_VERSION=0.13.7
ARG UV_SHA256=287491da03f2a785c70fa75b13e1f849918c2f2b5415fe84876b8214eeb792f9

LABEL org.opencontainers.image.title="xp-toolchain" \
      org.opencontainers.image.description="AlmaLinux 8 C++ toolchain for xp-pricer (glibc 2.28 floor)"

SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

# ---- compilers and system packages (RHEL 8 AppStream/PowerTools) ----
RUN dnf -y -q install dnf-plugins-core \
 && dnf config-manager --set-enabled powertools \
 && dnf -y -q install \
      "gcc-toolset-${GCC_TOOLSET}-gcc" "gcc-toolset-${GCC_TOOLSET}-gcc-c++" \
      "gcc-toolset-${GCC_TOOLSET}-binutils" \
      "clang-${CLANG_NEVR}" "clang-tools-extra-${CLANG_NEVR}" "compiler-rt-${CLANG_NEVR}" \
      "llvm-libs-${LLVM_LIBS_NEVR}" \
      python3.11 python3.11-devel python3.11-pip \
      git zip unzip tar xz curl perl perl-IPC-Cmd make pkgconf-pkg-config \
      binutils file which findutils diffutils patch \
 && alternatives --set python3 /usr/bin/python3.11 \
 && dnf clean all && rm -rf /var/cache/dnf

# gcc-toolset-13 on PATH without `scl enable` (non-interactive CI shells never source it).
ENV PATH=/opt/rh/gcc-toolset-${GCC_TOOLSET}/root/usr/bin:${PATH} \
    LD_LIBRARY_PATH=/opt/rh/gcc-toolset-${GCC_TOOLSET}/root/usr/lib64:/opt/rh/gcc-toolset-${GCC_TOOLSET}/root/usr/lib

# ---- build tools from upstream releases, checksum-verified ----
RUN curl -fsSL -o /tmp/cmake.tgz \
      "https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}/cmake-${CMAKE_VERSION}-linux-x86_64.tar.gz" \
 && echo "${CMAKE_SHA256}  /tmp/cmake.tgz" | sha256sum -c - \
 && mkdir -p /opt/cmake && tar -xzf /tmp/cmake.tgz -C /opt/cmake --strip-components=1 \
 && ln -s /opt/cmake/bin/cmake /opt/cmake/bin/ctest /opt/cmake/bin/cpack /usr/local/bin/ \
 && curl -fsSL -o /tmp/ninja.zip \
      "https://github.com/ninja-build/ninja/releases/download/v${NINJA_VERSION}/ninja-linux.zip" \
 && echo "${NINJA_SHA256}  /tmp/ninja.zip" | sha256sum -c - \
 && unzip -q /tmp/ninja.zip -d /usr/local/bin \
 && curl -fsSL -o /tmp/sccache.tgz \
      "https://github.com/mozilla/sccache/releases/download/${SCCACHE_VERSION}/sccache-${SCCACHE_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
 && echo "${SCCACHE_SHA256}  /tmp/sccache.tgz" | sha256sum -c - \
 && tar -xzf /tmp/sccache.tgz -C /usr/local/bin --strip-components=1 --wildcards '*/sccache' \
 && curl -fsSL -o /tmp/uv.tgz \
      "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-musl.tar.gz" \
 && echo "${UV_SHA256}  /tmp/uv.tgz" | sha256sum -c - \
 && tar -xzf /tmp/uv.tgz -C /usr/local/bin --strip-components=1 \
 && rm -f /tmp/*.tgz /tmp/*.zip

# ---- Python lint/CI tooling, versions taken from uv.lock (single source with pre-commit/dev) ----
COPY pyproject.toml uv.lock /tmp/xp/
COPY python/pyproject.toml /tmp/xp/python/
COPY python/service/pyproject.toml /tmp/xp/python/service/
RUN cd /tmp/xp \
 && uv export --frozen --no-default-groups --group lint --no-emit-project --no-emit-workspace \
      -o /tmp/requirements.txt \
 && uv pip install --system --python /usr/bin/python3.11 --require-hashes -r /tmp/requirements.txt \
 && rm -rf /tmp/xp /tmp/requirements.txt /root/.cache/uv

# ---- vcpkg at the manifest's builtin-baseline (image rebuilds when the baseline moves) ----
ENV VCPKG_ROOT=/opt/vcpkg \
    VCPKG_FORCE_SYSTEM_BINARIES=1 \
    VCPKG_DISABLE_METRICS=1 \
    VCPKG_DEFAULT_BINARY_CACHE=/cache/vcpkg-archives \
    SCCACHE_DIR=/cache/sccache
COPY vcpkg.json /tmp/vcpkg.json
RUN baseline="$(python3 -c 'import json; print(json.load(open("/tmp/vcpkg.json"))["builtin-baseline"])')" \
 && git clone --quiet --filter=blob:none https://github.com/microsoft/vcpkg "${VCPKG_ROOT}" \
 && git -C "${VCPKG_ROOT}" checkout --quiet "${baseline}" \
 && "${VCPKG_ROOT}/bootstrap-vcpkg.sh" -disableMetrics \
 && ln -s "${VCPKG_ROOT}/vcpkg" /usr/local/bin/vcpkg \
 && rm /tmp/vcpkg.json

# ---- unprivileged user for the devcontainer; CI may run as root. /cache is a volume mount. ----
RUN useradd --create-home --uid 1000 xp \
 && mkdir -p /cache/vcpkg-archives /cache/sccache && chmod -R 1777 /cache \
 && chown -R xp:xp "${VCPKG_ROOT}" \
 && git config --system --add safe.directory '*'

# ---- smoke test: the image fails to build if any pin drifted ----
RUN gcc --version | head -1 | grep -q " ${GCC_TOOLSET}\." \
 && clang --version | head -1 | grep -q " 17\.0\.6" \
 && clang-tidy --version | grep -q "17\.0\.6" \
 && cmake --version | head -1 | grep -q "${CMAKE_VERSION}" \
 && ninja --version | grep -qx "${NINJA_VERSION}" \
 && sccache --version | grep -q "${SCCACHE_VERSION#v}" \
 && uv --version | grep -q "${UV_VERSION}" \
 && python3 --version | grep -q "3\.11" \
 && clang-format --version | grep -q "18\.1\.8" \
 && ruff --version && vcpkg version | head -1 \
 && ldd --version | head -1 | grep -q "2\.28"

VOLUME ["/cache"]
WORKDIR /src
