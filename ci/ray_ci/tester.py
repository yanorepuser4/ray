import os
import sys
from typing import List, Optional
from enum import Enum

import yaml
import click

from ci.ray_ci.container import _DOCKER_ECR_REPO
from ci.ray_ci.tester_container import TesterContainer
from ci.ray_ci.utils import docker_login

# Gets the path of product/tools/docker (i.e. the parent of 'common')
bazel_workspace_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "")


class TestType(Enum):
    ASAN = "asan_tests"
    DATA_INTEGRATION = "data_integration"
    DEBUG = "debug_tests"
    DOC = "doctest"
    GPU = "gpu"
    POST_WHEEL = "post_wheel_build"
    KUBERAY = "kuberay_operator"
    SPARK_PLUGIN = "spark_plugin_tests"
    WORKER_CONTAINER = "worker-container"


@click.command()
@click.argument("targets", required=True, type=str, nargs=-1)
@click.argument("team", required=True, type=str, nargs=1)
@click.option(
    "--workers",
    default=1,
    type=int,
    help=("Number of concurrent test jobs to run."),
)
@click.option(
    "--worker-id",
    default=0,
    type=int,
    help=("Index of the concurrent shard to run."),
)
@click.option(
    "--parallelism-per-worker",
    default=1,
    type=int,
    help=("Number of concurrent test jobs to run per worker."),
)
@click.option(
    "--run-flaky-tests",
    is_flag=True,
    show_default=True,
    default=False,
    help=("Run flaky tests."),
)
@click.option(
    "--test-env",
    multiple=True,
    type=str,
    help="Environment variables to set for the test.",
)
@click.option(
    "--test-type",
    default=None,
    type=click.Choice([t.value for t in TestType]),
)
@click.option(
    "--build-name",
    type=str,
    help="Name of the build used to run tests",
)
def main(
    targets: List[str],
    team: str,
    workers: int,
    worker_id: int,
    parallelism_per_worker: int,
    run_flaky_tests: bool,
    test_env: List[str],
    test_type: Optional[str],
    build_name: Optional[str],
) -> None:
    if not bazel_workspace_dir:
        raise Exception("Please use `bazelisk run //ci/ray_ci`")
    os.chdir(bazel_workspace_dir)
    docker_login(_DOCKER_ECR_REPO.split("/")[0])

    container = _get_container(
        team, workers, worker_id, parallelism_per_worker, build_name
    )
    if run_flaky_tests:
        test_targets = _get_flaky_tests(team)
    else:
        test_targets = _get_tests(
            container,
            targets,
            team,
            test_type,
        )
    success = container.run_tests(test_targets, test_env)
    sys.exit(0 if success else 1)


def _get_container(
    team: str,
    workers: int,
    worker_id: int,
    parallelism_per_worker: int,
    build_name: Optional[str] = None,
) -> TesterContainer:
    shard_count = workers * parallelism_per_worker
    shard_start = worker_id * parallelism_per_worker
    shard_end = (worker_id + 1) * parallelism_per_worker

    return TesterContainer(
        build_name or f"{team}build",
        shard_count=shard_count,
        shard_ids=list(range(shard_start, shard_end)),
    )


def _get_tests_by_tag_query(targets: List[str], tag: str) -> str:
    test_query = " union ".join([f"tests({target})" for target in targets])
    return f"attr(tags, '{tag}', {test_query})"


def _get_tests_by_tag(
    container: TesterContainer,
    targets: List[str],
    tag: str,
) -> List[str]:
    test_query = _get_tests_by_tag_query(targets, tag)
    return (
        container.run_script_with_output(
            [
                f'bazel query "{test_query}"',
            ]
        )
        .decode("utf-8")
        .split("\n")
    )


def _get_tests(
    container: TesterContainer,
    targets: str,
    team: str,
    test_type: Optional[str] = None,
    yaml_dir: Optional[str] = None,
) -> List[str]:
    """
    Get all test targets that are not flaky
    """
    all_tests = _get_tests_by_tag(container, targets, f"team:{team}\\\\b")
    # exclude flaky, manual and civ1 tests by default
    excluded = (
        _get_flaky_tests(team, yaml_dir)
        + _get_tests_by_tag(container, targets, "xcommit")
        + _get_tests_by_tag(container, targets, "manual")
    )

    if test_type:
        # if test type is defined, only include tests that particular types (e.g. debug)
        type_tests = _get_tests_by_tag(container, targets, test_type)
        included = [test for test in all_tests if test in type_tests]
    else:
        # otherwise, exclude all tests of any types (e.g. debug, asan)
        for test_type in TestType:
            type_tests = _get_tests_by_tag(container, targets, test_type.value)
            excluded += type_tests
        included = all_tests

    return [test for test in included if test not in excluded]


def _get_flaky_tests(team: str, yaml_dir: Optional[str] = None) -> List[str]:
    """
    Get all test targets that are flaky
    """
    if not yaml_dir:
        yaml_dir = os.path.join(bazel_workspace_dir, "ci/ray_ci")

    with open(f"{yaml_dir}/{team}.tests.yml", "rb") as f:
        flaky_tests = yaml.safe_load(f)["flaky_tests"]

    return flaky_tests
