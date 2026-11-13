"""Test packaged SDK/core ABI and record actual optional capabilities and hashes."""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

CORE = {
    "dls_info", "dls_last_error", "dls_engine_open", "dls_engine_load",
    "dls_engine_cards", "dls_engine_decks", "dls_engine_free", "dls_game_new",
    "dls_game_decision", "dls_game_seat", "dls_game_apply", "dls_game_free",
    "dls_bot_new", "dls_bot_choose", "dls_bot_version", "dls_bot_free",
}
OPTIONAL = {"dls_game_sample", "dls_game_clone"}


def symbols(path):
    return set(re.findall(r"\bdls_[a-z_]+(?=\s*\()", path.read_text(encoding="utf-8")))


def payload_hashes(directory):
    """Hash exact packaged bytes; the digest covers sorted relative paths too."""
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError("SDK payload must be a real directory")
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("SDK payload symlinks are not supported")
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif not path.is_dir():
            raise RuntimeError("SDK payload contains a non-regular file")
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return {"files": files, "sha256": hashlib.sha256(encoded).hexdigest(),
            "digest_format": "sha256 of UTF-8 canonical JSON files map (sorted keys, compact separators, ASCII escapes)"}


def check(directory, sdk, library_name, expected_engine, expected_abi):
    payload = payload_hashes(sdk)
    header = directory / "decklogic_simlib.h"
    if header.is_symlink() or not header.is_file():
        raise RuntimeError("Packaged header must be a regular file")
    demo = sdk / "sample/demo/sim_DEMO.json"
    if not demo.is_file():
        raise RuntimeError("Required synthetic DEMO pack missing from SDK")
    # Importing the SDK must not add pycache files to the package after hashing.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(sdk / "simlib/python"))
    import simlib

    library_file = directory / library_name
    lib = simlib.Library(str(library_file.resolve()))
    info = lib.info
    assert info["engine"] == expected_engine, "engine mismatch"
    assert info["abi"] == expected_abi, "ABI mismatch"
    assert info["protocol"] == "decklogic-bot/1", "protocol mismatch"
    assert info["library"] == "decklogic-simlib/1", "library interface mismatch"
    packaged = symbols(directory / "decklogic_simlib.h")
    client = symbols(sdk / "simlib/include/decklogic_simlib.h")
    assert CORE <= packaged and CORE <= client, "core header declaration missing"
    required = (packaged | client | CORE) - OPTIONAL
    available = {name: getattr(lib._dll, name, None) is not None for name in sorted(required | OPTIONAL)}
    missing = [name for name in sorted(required) if not available[name]]
    assert not missing, "required library exports missing: " + ", ".join(missing)
    executable = directory / ("botkit.exe" if os.name == "nt" else "botkit")
    subprocess.run([str(executable.resolve()), "--help"], check=True, capture_output=True)
    engine = lib.engine(str(demo.resolve()))
    decks = engine.decks()
    assert len(decks) >= 2 and all(len(deck["main"]) == 40 for deck in decks)
    game = engine.game([decks[0]["main"], decks[1]["main"]], seed=7, labels=False)
    bots = [game.bot("quick", seat=seat, seed=7) for seat in (0, 1)]
    steps = 0
    while (decision := game.decision())["type"] == "decision":
        action = bots[decision["seat"]].choose()
        assert action in {choice["id"] for choice in decision["actions"]}
        game.apply(action)
        steps += 1
        assert steps <= 10000, "demo decision bound exceeded"
    assert decision["result"] in ("win", "draw"), "demo did not complete before engine cap"
    gameplay = {"status": "passed", "decisions": steps, "result": decision["result"],
                "pack_checksum": engine.cards()["pack_checksum"]}
    for bot in bots:
        bot.close()
    game.close()
    engine.close()
    return {
        "platform": os.environ.get("PLATFORM", sys.platform), "library_info": info,
        "capabilities": {"required": sorted(required),
                         "optional": {name: available[name] for name in sorted(OPTIONAL)},
                         "packaged_header": sorted(packaged), "sdk_header": sorted(client)},
        "binaries": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in (library_file, executable)},
        "header": {"path": header.name, "sha256": hashlib.sha256(header.read_bytes()).hexdigest()},
        "sdk_payload": payload,
        "demo": gameplay,
    }


if __name__ == "__main__":
    directory = pathlib.Path(os.environ["DIR"])
    sdk = pathlib.Path(os.environ.get("SDK_ROOT", str(directory / "sdk")))
    result = check(directory, sdk, os.environ["LIB"], os.environ["ENGINE"], int(os.environ["ABI"]))
    # Workflow supplies the content/provenance identity; local audits may only print.
    manifest = directory / "release-manifest.json"
    if manifest.is_file():
        identity = json.loads(manifest.read_text(encoding="utf-8"))
        identity["artifact"] = result
        manifest.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
