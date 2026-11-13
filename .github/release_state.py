"""Read-only release metadata gate; never repairs or mutates a release."""
import argparse
import json
from pathlib import Path


RECOVERY = (
    "Stop and review the existing release's identity and assets. An authorized "
    "operator must recover the same verified build or choose a replacement "
    "under the release process; this workflow will not overwrite or repair it."
)


def required_assets(tag):
    return {
        f"decklogic-botkit-{tag}-linux-x86_64.tar.gz",
        f"decklogic-botkit-{tag}-windows-x86_64.zip",
        f"decklogic-botkit-{tag}-macos-arm64.tar.gz",
        "release-manifest.json", "SHA256SUMS",
    }


def classify(pages, tag):
    """Return absent/complete from gh api --paginate --slurp release metadata.

    Completeness here is metadata only, not a verification of downloaded bytes.
    """
    if not isinstance(pages, list) or not pages:
        raise ValueError("Expected a nonempty list of successful API pages")
    releases = []
    for page in pages:
        if not isinstance(page, list):
            raise ValueError("Expected release-list API pages, not an API error")
        for release in page:
            if not isinstance(release, dict) or not isinstance(release.get("tag_name"), str):
                raise ValueError("Invalid release metadata")
            releases.append(release)
    matches = [r for r in releases if r["tag_name"] == tag]
    if not matches:
        return "absent"
    if len(matches) != 1:
        raise ValueError("Duplicate release tags. " + RECOVERY)
    release = matches[0]
    if (release.get("draft") is not False or release.get("prerelease") is not False
            or not isinstance(release.get("published_at"), str)
            or not release["published_at"]):
        raise ValueError("Existing release is not a published stable release. " + RECOVERY)
    assets = release.get("assets")
    if not isinstance(assets, list) or any(not isinstance(a, dict) for a in assets):
        raise ValueError("Invalid release asset metadata. " + RECOVERY)
    for name in sorted(required_assets(tag)):
        matching = [a for a in assets if a.get("name") == name]
        if (len(matching) != 1 or matching[0].get("state") != "uploaded"
                or type(matching[0].get("size")) is not int or matching[0]["size"] <= 0):
            raise ValueError(f"Missing, duplicate, empty or unfinished asset: {name}. " + RECOVERY)
    return "complete"


def latest_policy(event, private_ref, manual_promote=False):
    if type(manual_promote) is not bool:
        raise ValueError("Promotion must be a boolean")
    if event == "workflow_dispatch":
        return manual_promote
    if event == "schedule" and private_ref == "main":
        return True
    raise ValueError("Unsupported release event/ref policy")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--private-ref", required=True)
    parser.add_argument("--promote-latest", choices=("true", "false"), default="false")
    parser.add_argument("--github-output", required=True)
    args = parser.parse_args()
    try:
        state = classify(json.loads(Path(args.metadata).read_text(encoding="utf-8")), args.tag)
        latest = latest_policy(args.event, args.private_ref, args.promote_latest == "true")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Release check failed: {error}\n")
    with Path(args.github_output).open("a", encoding="utf-8") as output:
        output.write(f"build={str(state == 'absent').lower()}\nlatest={str(latest).lower()}\n")
    print(f"Release state: {state}; latest on creation: {str(latest).lower()}")


if __name__ == "__main__":
    main()
