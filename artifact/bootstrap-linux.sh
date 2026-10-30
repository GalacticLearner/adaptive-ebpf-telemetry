#!/usr/bin/env bash
# Explicit setup for a disposable/authorized Ubuntu 24.04 Linux host.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -m)" != x86_64 ]]; then echo 'x86-64 host required' >&2; exit 2; fi
mkdir -p state/bootstrap build/deps .deps
# Resolve each Ubuntu archive package to an exact version BEFORE installation;
# preserve the resolution and installed versions for the actual host lock.
packages=(build-essential clang-18 llvm-18 libelf-dev zlib1g-dev pkg-config linux-tools-common python3-venv curl ca-certificates)
resolved=()
for package in "${packages[@]}"; do
  version=$(apt-cache policy "$package" | awk '/Candidate:/ {print $2;exit}')
  if [[ -z "$version" || "$version" == '(none)' ]]; then echo "No supported archive candidate: $package" >&2; exit 2; fi
  resolved+=("$package=$version")
done
printf '%s\n' "${resolved[@]}" > state/bootstrap/apt-resolved.txt
sudo apt-get install --no-install-recommends "${resolved[@]}"
# Matching bpftool is a target feature-discovery dependency, never a fabricated lock.
if ! command -v bpftool >/dev/null; then
  package="linux-tools-$(uname -r)"
  version=$(apt-cache policy "$package" | awk '/Candidate:/ {print $2;exit}')
  if [[ -z "$version" || "$version" == '(none)' ]]; then echo "Install an authorized bpftool for this actual kernel; no kernel replacement is performed." >&2; exit 2; fi
  sudo apt-get install --no-install-recommends "$package=$version"
fi
archive=build/deps/libbpf-v1.5.1.tar.gz
curl --fail --location --output "$archive" https://github.com/libbpf/libbpf/archive/refs/tags/v1.5.1.tar.gz
printf '%s  %s\n' e5ff89750e48ab5ecdfc02a759aa0dacd1e7980e98e16bdb4bfa8ff0b3b4b98f "$archive" | sha256sum -c -
tar -xzf "$archive" -C build/deps
prefix="$PWD/.deps/libbpf-1.5.1"
make -C build/deps/libbpf-1.5.1/src BUILD_STATIC_ONLY=1 PREFIX="$prefix" LIBDIR="$prefix/lib" INCLUDEDIR="$prefix/include" install
mkdir -p "$prefix/licenses"
cp build/deps/libbpf-1.5.1/LICENSE* "$prefix/licenses/"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-analysis.lock
dpkg-query -W > state/bootstrap/dpkg-installed.txt
PKG_CONFIG_PATH="$prefix/lib/pkgconfig" make CLANG=clang-18 build
printf '\nNext: sudo .venv/bin/python -m runner doctor --output state/host.json\n'
