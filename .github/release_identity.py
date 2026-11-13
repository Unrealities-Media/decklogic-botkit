"""Content identity for a kit release; Git SHAs pin provenance, not rebuild scope."""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import tarfile
import zipfile

# Whole crate trees conservatively cover build.rs, cards, and include_* assets.
# The last paths cover compile-time includes outside those crate directories.
PRIVATE_INPUTS = (
    "Cargo.toml", "Cargo.lock", "rust-toolchain.toml", ".cargo",
    "src-tauri/sim", "src-tauri/botkit", "src-tauri/simlib",
    "bots/protocol", "docs/research/sim66-hob-drafted-league",
)
REQUIRED_INPUTS = set(PRIVATE_INPUTS[:3]) | {
    "src-tauri/sim", "src-tauri/botkit", "src-tauri/simlib",
}


def git(repo, *args):
    # Never expose private Git stderr or file contents through a public traceback.
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Git identity lookup failed; inspect the pinned checkout privately")
    return result.stdout.strip()


def identity(private, public, private_ref="HEAD", public_ref="HEAD"):
    private_sha = git(private, "rev-parse", "--verify", private_ref + "^{commit}")
    public_sha = git(public, "rev-parse", "--verify", public_ref + "^{commit}")
    trees = {}
    for path in PRIVATE_INPUTS:
        entry = git(private, "ls-tree", private_sha, "--", path)
        if not entry and path in REQUIRED_INPUTS:
            raise RuntimeError("Required build input absent: " + path)
        trees[path] = entry.split("\t", 1)[0] if entry else None
    public_tree = git(public, "rev-parse", public_sha + "^{tree}")
    version = git(private, "show", private_sha + ":src-tauri/sim/src/version.rs")
    engine = re.search(r'pub const ENGINE_VERSION: &str = "([A-Za-z0-9._-]+)"', version)
    abi = re.search(r"pub const ENGINE_ABI: u32 = ([0-9]+)", version)
    if not engine or not abi:
        raise RuntimeError("Missing or invalid engine stamp")
    inputs = {"private": trees, "public_tree": public_tree}
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": "decklogic-kit-release/1", "kit_sha256": digest,
        "tag": engine[1] + "-kit-" + digest[:16],
        "private_commit": private_sha, "public_commit": public_sha,
        "engine": engine[1], "abi": int(abi[1]),
        "protocol": "decklogic-bot/1", "library": "decklogic-simlib/1",
        "inputs": inputs,
    }


def collect_archives(directory, expected_tag):
    archives = sorted(path for path in pathlib.Path(directory).iterdir()
                      if path.name.endswith((".zip", ".tar.gz")))
    if len(archives) != 3:
        raise RuntimeError("Expected exactly three platform archives")
    base, artifacts = None, []
    for path in archives:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                names = [name for name in archive.namelist() if name.count("/") == 1 and name.endswith("/release-manifest.json")]
                if len(names) != 1:
                    raise RuntimeError("Missing or duplicate artifact manifest")
                record = json.loads(archive.read(names[0]))
        else:
            with tarfile.open(path, "r:gz") as archive:
                names = [name for name in archive.getnames() if name.count("/") == 1 and name.endswith("/release-manifest.json")]
                if len(names) != 1:
                    raise RuntimeError("Missing or duplicate artifact manifest")
                record = json.load(archive.extractfile(names[0]))
        artifact = record.pop("artifact")
        if record["tag"] != expected_tag or (base is not None and record != base):
            raise RuntimeError("Artifact source identities differ")
        base = record
        artifacts.append({"archive": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **artifact})
    if {item["platform"] for item in artifacts} != {"linux-x86_64", "windows-x86_64", "macos-arm64"}:
        raise RuntimeError("Expected one artifact per platform")
    return {**base, "artifacts": artifacts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private")
    parser.add_argument("--public")
    parser.add_argument("--collect", help="directory of the three completed platform archives")
    parser.add_argument("--tag", help="expected kit tag when collecting")
    parser.add_argument("--out", required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args()
    if args.collect:
        if not args.tag:
            parser.error("--collect requires --tag")
        result = collect_archives(args.collect, args.tag)
    else:
        if not args.private or not args.public:
            parser.error("identity requires --private and --public")
        result = identity(args.private, args.public)
    pathlib.Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as stream:
            for key in ("tag", "kit_sha256", "private_commit", "public_commit", "engine", "abi"):
                stream.write(f"{key}={result[key]}\n")
    print(result["tag"])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error)) from None
