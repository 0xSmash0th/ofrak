#!/bin/bash
#
# Run the OFRAK Ghidra server in Ghidra's foreground "console" mode.
#
# Unlike run_ghidra_server.sh (which uses `svrInstall` + a systemd service and therefore
# requires root), this uses `ghidraSvr console`, which Ghidra permits for a normal,
# non-root user. First-run repository/user setup is performed against the running console
# server if it is not already present; that setup only writes to the (user-owned) Ghidra
# repositories directory, so no elevation is needed at any step.
#
# Args match run_ghidra_server.sh:
#   $1 GHIDRA_PATH  $2 OFRAK_GHIDRA_SCRIPTS_PATH  $3 GHIDRA_USER  $4 GHIDRA_PASS
#   $5 GHIDRA_REPO_HOST  $6 GHIDRA_REPO_PORT
set -e

GHIDRA_PATH=$1
OFRAK_GHIDRA_SCRIPTS_PATH=$2
GHIDRA_USER=$3
GHIDRA_PASS=$4
GHIDRA_REPO_HOST=$5
GHIDRA_REPO_PORT=$6

cd "${GHIDRA_PATH}"

# Ensure the repository user exists. svrAdmin edits the user-owned user file, so no root is
# needed; harmless if the user already exists.
./server/svrAdmin -add "${GHIDRA_USER}" >/dev/null 2>&1 || true

# Launch Ghidra Server in foreground console mode (no root), backgrounded so this script can
# finish first-run setup; stop it whenever this script exits.
./server/ghidraSvr console &
GHIDRA_SVR_PID=$!
cleanup() {
  kill "${GHIDRA_SVR_PID}" 2>/dev/null || true
  wait "${GHIDRA_SVR_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# Wait (up to 60s) for the repository port to accept connections.
for _ in $(seq 1 60); do
  if (exec 3<>"/dev/tcp/127.0.0.1/${GHIDRA_REPO_PORT}") 2>/dev/null; then
    exec 3>&- 3<&-
    break
  fi
  sleep 1
done

# First run only: create the 'ofrak' repository (no root; talks to the running server).
if [ ! -d "./repositories/ofrak" ]; then
  ./support/analyzeHeadless . dummy -postScript CreateRepository.java \
    "${GHIDRA_USER}" "${GHIDRA_PASS}" "${GHIDRA_REPO_HOST}" "${GHIDRA_REPO_PORT}" \
    -scriptPath "${OFRAK_GHIDRA_SCRIPTS_PATH}" -deleteProject -noanalysis
  if ./server/svrAdmin --help 2>&1 | grep -q '\-grant'; then
    ./server/svrAdmin -grant "${GHIDRA_USER}" +a ofrak || true
  fi
fi

echo "OFRAK Ghidra server running in console mode (no root). Press Ctrl-C to stop."
# Hand control to the foreground server; block until it exits.
wait "${GHIDRA_SVR_PID}"
