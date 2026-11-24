#!/usr/bin/env bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo " Scientific American Unpaywalled Editorial Reader & Archive"
echo "=========================================================="
echo "Starting local offline reader server..."

PORT=8765
python3 -m http.server $PORT --directory dist > /dev/null 2>&1 &
SERVER_PID=$!

sleep 1
open "http://localhost:$PORT"

echo "Reader running at http://localhost:$PORT"
echo "Press Ctrl+C to stop the server."

trap "kill $SERVER_PID 2>/dev/null; exit" INT TERM
wait $SERVER_PID
