#!/bin/bash
# Script to run DREAMPlace inside Docker container
# Usage: ./run_dreamplace.sh <benchmark>
# Example: ./run_dreamplace.sh adaptec1

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <benchmark>"
    echo "Example: $0 adaptec1"
    echo "         $0 bigblue1"
    exit 1
fi

BENCHMARK=$1
CONTAINER_NAME="dreamplace_dev"

echo "=========================================="
echo "Running DREAMPlace for: $BENCHMARK"
echo "=========================================="
echo ""

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Error: Container '$CONTAINER_NAME' does not exist!"
    echo "Please run first:"
    echo "  docker run --gpus all -it --name dreamplace_dev -v \"\$(pwd)/DREAMPlace\":/DREAMPlace limbo018/dreamplace:cuda bash"
    exit 1
fi

# Start container if not running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Starting container '$CONTAINER_NAME'..."
    docker start $CONTAINER_NAME
    sleep 2
fi

echo "Running DREAMPlace in container..."
echo ""

# Execute DREAMPlace
docker exec -i $CONTAINER_NAME bash -c "cd /DREAMPlace/install && python dreamplace/Placer.py test/ispd2005/${BENCHMARK}.json"

echo ""
echo "=========================================="
echo "DREAMPlace completed for: $BENCHMARK"
echo "=========================================="
