import os
import subprocess

import click


@click.command()
def main() -> None:
    notify_yml = {
        "steps": [
            {
                # This is a dummy command that always succeeds so that buildkite
                # accepts the pipeline definition.
                "command": "exit 0"
            }
        ],
        "notify": [
            {
                "email": os.environ["BUILDKITE_BUILD_CREATOR_EMAIL"],
                "if": 'build.state == "failing"',
            }
        ],
    }

    subprocess.run(
        [
            "buildkite-agent",
            "pipeline",
            "upload",
        ],
        input=bytes(str(notify_yml), "utf-8"),
        check=True,
    )


if __name__ == "__main__":
    main()
