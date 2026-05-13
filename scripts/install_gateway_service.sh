#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="quadruped-ws-gateway.service"
REPO_DIR="/home/orangepi/quadruped_dev_sdk"
SERVICE_SRC="${REPO_DIR}/systemd/${SERVICE_NAME}"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

if [ ! -f "${SERVICE_SRC}" ]; then
  echo "Missing service file: ${SERVICE_SRC}" >&2
  exit 1
fi

sudo cp "${SERVICE_SRC}" "${SERVICE_DST}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl --no-pager --full status "${SERVICE_NAME}"
