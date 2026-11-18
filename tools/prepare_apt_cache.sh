#!/usr/bin/env bash
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:-$PWD}"
CACHE="$ROOT/.raws-apt-cache"
mkdir -p "$CACHE/archives/partial"
sudo install -d -o _apt -g root -m 0755 "$CACHE/archives" "$CACHE/archives/partial"
sudo chown -R _apt:root "$CACHE/archives"
sudo find "$CACHE/archives" -type d -exec chmod 0755 {} +
sudo find "$CACHE/archives" -type f -exec chmod 0644 {} +
sudo tee /etc/apt/apt.conf.d/99raws-workspace-cache >/dev/null <<APTCONF
Dir::Cache::archives "$CACHE/archives";
Binary::apt::APT::Keep-Downloaded-Packages "true";
APT::Keep-Downloaded-Packages "true";
Dpkg::Use-Pty "0";
Acquire::Retries "3";
Acquire::Languages "none";
Acquire::http::Timeout "60";
Acquire::https::Timeout "60";
APTCONF
printf 'RAWS_APT_CACHE ready deb_count=%s\n' "$(find "$CACHE/archives" -name '*.deb' | wc -l)"
