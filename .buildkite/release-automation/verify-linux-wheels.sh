#!/bin/bash

set -euo pipefail

set -x

export PYTHON_VERSION="${PYTHON_VERSION}"

get_ray_version() {
    VERSION=$(python python/ray/_version.py | awk '{print $1}')
    if [[ "$VERSION" == "3.0.0.dev0" ]]; then
        echo "Not a release version. Exiting.." >&2
        exit 1
    fi
    echo "$VERSION"
}

if [[ -z "$RAY_VERSION" ]]; then
    FETCHED_RAY_VERSION=$(get_ray_version)
    export RAY_VERSION="${FETCHED_RAY_VERSION}"
fi

if [[ -z "$BUILDKITE_COMMIT" ]]; then
    echo "BUILDKITE_COMMIT environment variable is not set"
    exit 1
fi

export PATH="/usr/local/bin/miniconda3/bin:$PATH"
source "/usr/local/bin/miniconda3/etc/profile.d/conda.sh"

conda create -n rayio python="${PYTHON_VERSION}" -y

conda activate rayio

pip install \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple \
    "ray[cpp]==$RAY_VERSION"

(
    cd release/util
    python sanity_check.py --ray_version="$RAY_VERSION" --ray_commit="$BUILDKITE_COMMIT"
)

(
    cd release/util
    bash sanity_check_cpp.sh
)
