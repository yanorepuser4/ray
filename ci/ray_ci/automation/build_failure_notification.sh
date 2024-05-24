#!/bin/bash

set -exo pipefail

echo "{'notify': [{'email': '${BUILDKITE_BUILD_CREATOR_EMAIL}','if': 'build.state == \"failing\"'}]}" | buildkite-agent pipeline upload
