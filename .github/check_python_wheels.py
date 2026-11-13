"""Read-only checks of built public Python wheels; no build/install/network work."""
import argparse
import ast
import configparser
from email.parser import BytesParser
from pathlib import Path
import sys
import zipfile


MODULES = {
    "decklogic-botlib": {"botlib.py"},
    "decklogic-simlib": {"simlib.py", "simlib_env.py", "simlib_traces.py", "lookahead_bot.py"},
}
CONSOLE_SCRIPTS = {
    "simlib-traces": "simlib_traces:main",
    "simlib-lookahead": "lookahead_bot:main",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(directory, license_file):
    wheels = sorted(directory.glob("*.whl"))
    require(len(wheels) == 2, "expected exactly the botlib and simlib wheels")
    expected_license = license_file.read_bytes()
    seen = set()
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)), f"{wheel.name}: duplicate archive members")
            metadata_files = [name for name in names if name.endswith(".dist-info/METADATA")]
            require(len(metadata_files) == 1, f"{wheel.name}: expected one METADATA file")
            metadata_path = metadata_files[0]
            metadata = BytesParser().parsebytes(archive.read(metadata_path))
            name = metadata.get("Name")
            require(name in MODULES and name not in seen, f"{wheel.name}: unexpected or duplicate project")
            seen.add(name)
            require(metadata.get_all("License-Expression") == ["MIT"], f"{name}: expected MIT License-Expression")
            require(metadata.get_all("License-File") == ["LICENSE"], f"{name}: expected one License-File: LICENSE")
            dist_info = metadata_path.rsplit("/", 1)[0]
            license_path = dist_info + "/licenses/LICENSE"
            license_members = [item for item in names if item.startswith(dist_info + "/licenses/") and not item.endswith("/")]
            require(license_members == [license_path], f"{name}: expected exactly one packaged license file")
            require(archive.read(license_path) == expected_license, f"{name}: license bytes differ from repository LICENSE")
            for module in sorted(MODULES[name]):
                require(module in names, f"{name}: missing module {module}")
                # Compile without execution to catch syntax unsupported by this Python.
                compile(archive.read(module), module, "exec")
            if name == "decklogic-botlib":
                tree = ast.parse(archive.read("botlib.py"), filename="botlib.py")
                versions = [node.value for node in tree.body if isinstance(node, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == "__version__"
                                    for target in node.targets)]
                require(len(versions) == 1 and isinstance(versions[0], ast.Constant)
                        and isinstance(versions[0].value, str)
                        and versions[0].value == metadata.get("Version"),
                        "botlib: top-level literal __version__ must match wheel Version")
            if name == "decklogic-simlib":
                entry_path = dist_info + "/entry_points.txt"
                require(entry_path in names, "simlib: missing console entry metadata")
                entries = configparser.ConfigParser(interpolation=None)
                entries.read_string(archive.read(entry_path).decode("utf-8"))
                require(entries.has_section("console_scripts"), "simlib: missing console_scripts section")
                for command, target in CONSOLE_SCRIPTS.items():
                    require(entries.get("console_scripts", command, fallback=None) == target,
                            f"simlib: missing or incorrect {command} entry point")
    require(seen == set(MODULES), "expected both public Python projects")
    print("Python wheels passed: both projects, module syntax, MIT license bytes and simlib console metadata")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel_directory", type=Path)
    parser.add_argument("repository_license", type=Path)
    args = parser.parse_args()
    try:
        check(args.wheel_directory, args.repository_license)
    except (OSError, ValueError, KeyError, SyntaxError, configparser.Error, zipfile.BadZipFile) as error:
        print(f"Python wheel check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
