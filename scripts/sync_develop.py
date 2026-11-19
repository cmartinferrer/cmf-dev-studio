"""Synchronize a published release into develop through a protected pull request."""

import argparse
import json
import re
import subprocess


def run(*args: str) -> str:
    """Execute a command without a shell and return its output."""
    return subprocess.check_output(args, text=True).strip()


def ancestor(older: str, newer: str) -> bool:
    """Check ancestry, distinguishing Git errors from a negative result."""
    result = subprocess.run(["git", "merge-base", "--is-ancestor", older, newer])
    if result.returncode not in (0, 1):
        result.check_returncode()
    return result.returncode == 0


def synchronize(tag: str) -> None:
    """Create or reuse a release-specific synchronization pull request."""
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag):
        raise ValueError("Expected vX.Y.Z")
    release = json.loads(
        run("gh", "release", "view", tag, "--json", "isDraft,isPrerelease")
    )
    if release["isDraft"] or release["isPrerelease"]:
        raise ValueError("Expected a published stable release")
    run("git", "fetch", "origin", "--tags", "--prune")
    target = run("git", "rev-parse", f"refs/tags/{tag}^{{commit}}")
    if not ancestor(target, "origin/main"):
        raise ValueError("Release tag is not an ancestor of main")
    if ancestor(target, "origin/develop"):
        print(f"develop already contains {tag}")
        return

    branch = f"sync/release-{tag}"
    remote = f"refs/remotes/origin/{branch}"
    existing = run("git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}")
    run("git", "config", "user.name", "CMF Dev Studio Release Bot")
    run("git", "config", "user.email", "release-bot@users.noreply.github.com")
    if existing:
        run("git", "fetch", "origin", f"refs/heads/{branch}:{remote}")
        if not ancestor(target, remote):
            raise ValueError("Existing synchronization branch does not contain release")
        run("git", "switch", "--detach", remote)
        run("git", "merge", "--no-edit", "origin/develop")
    else:
        run("git", "switch", "--detach", "origin/develop")
        run("git", "merge", "--no-edit", target)
    # No force push: concurrent changes must be resolved by a retry.
    run("git", "push", "origin", f"HEAD:refs/heads/{branch}")
    prs = json.loads(
        run(
            "gh",
            "pr",
            "list",
            "--base",
            "develop",
            "--head",
            branch,
            "--state",
            "open",
            "--json",
            "number,headRefName",
        )
    )
    if len(prs) > 1:
        raise ValueError("Multiple synchronization pull requests found")
    if prs:
        pr = str(prs[0]["number"])
    else:
        pr = run(
            "gh",
            "pr",
            "create",
            "--base",
            "develop",
            "--head",
            branch,
            "--title",
            f"chore: sync {tag} into develop",
            "--body",
            f"Synchronize published release {tag} into develop. "
            "Required checks and branch protection remain enforced.",
        )
    run("gh", "pr", "merge", pr, "--auto", "--merge")
    print(f"Synchronization requested: {pr}")


def main() -> None:
    """Read the release tag from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    synchronize(parser.parse_args().tag)


if __name__ == "__main__":
    main()
