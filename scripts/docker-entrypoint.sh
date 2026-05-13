#!/usr/bin/env bash
set -euo pipefail

cd /opt/quadruped_dev_sdk

run_ws() {
  python3 tools/ws_gateway.py \
    --dog-ip "${DOG_IP}" \
    --dog-port "${DOG_PORT}" \
    --listen-host "${LISTEN_HOST}" \
    --listen-port "${LISTEN_PORT}" \
    --web-root "${WEB_ROOT}"
}

run_ws_mock() {
  python3 tools/ws_gateway.py \
    --mock \
    --dog-ip "${DOG_IP}" \
    --dog-port "${DOG_PORT}" \
    --listen-host "${LISTEN_HOST}" \
    --listen-port "${LISTEN_PORT}" \
    --web-root "${WEB_ROOT}"
}

case "${1:-ws}" in
  ws)
    run_ws
    ;;
  ws-mock | mock)
    run_ws_mock
    ;;
  example)
    exec ./bin/example "${@:2}"
    ;;
  keyboard)
    exec ./bin/keyboard_test "${@:2}"
    ;;
  imu)
    exec ./bin/imu_client_example "${@:2}"
    ;;
  bash | sh)
    exec "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
