"""Synthetic stdio starter smoke only; not host qualification or game simulation."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def check(command, transcript, timeout=10):
    messages = [json.loads(line[2:]) for line in transcript.read_text(encoding="utf-8").splitlines()
                if line.startswith("> ")]
    if not messages or messages[0].get("type") != "hello":
        raise ValueError("fixture must start with hello")
    if sum(m.get("type") == "hello" for m in messages) != 1:
        raise ValueError("fixture must contain exactly one hello")
    decisions = [m for m in messages if m.get("type") == "decision"]
    if not decisions or not any(m.get("type") == "future_optional_message" for m in messages):
        raise ValueError("fixture must cover decisions and an unknown message")
    wire = "".join(json.dumps(message) + "\n" for message in messages)
    runs = []
    for attempt in range(2):
        try:
            result = subprocess.run(command, input=wire, capture_output=True,
                                    text=True, encoding="utf-8", timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise ValueError(f"run {attempt + 1}: completion exceeded {timeout}s") from error
        if result.returncode:
            raise ValueError(f"run {attempt + 1}: process exited {result.returncode}: {result.stderr[:1000]}")
        try:
            replies = [json.loads(line) for line in result.stdout.splitlines()]
        except json.JSONDecodeError as error:
            raise ValueError(f"run {attempt + 1}: stdout must contain only JSON lines") from error
        if len(replies) != len(decisions) + 1 or any(not isinstance(r, dict) for r in replies):
            raise ValueError("expected exactly one ready followed by one action per decision")
        ready = replies[0]
        if (ready.get("type") != "ready" or ready.get("protocol") != messages[0]["protocol"]
                or not isinstance(ready.get("name"), str) or not ready["name"]
                or not isinstance(ready.get("version"), str) or not ready["version"]):
            raise ValueError("invalid ready reply")
        answers = []
        for decision, reply in zip(decisions, replies[1:]):
            if (reply.get("type") != "action" or type(reply.get("n")) is not int
                    or reply["n"] != decision["n"] or type(reply.get("id")) is not int
                    or reply["id"] not in [action["id"] for action in decision["actions"]]):
                raise ValueError(f"invalid action reply for decision {decision['n']}")
            answers.append((reply["n"], reply["id"]))
        runs.append(answers)
    if runs[0] != runs[1]:
        raise ValueError("repeated synthetic input produced different action answers")
    print(f"Synthetic stdio smoke passed: {len(decisions)} decisions, unknown message, two deterministic runs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", type=Path,
                        default=Path(__file__).resolve().parents[1] / "protocol/synthetic-transcript.txt")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- executable [arguments]")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not 0 < args.timeout <= 60:
        parser.error("provide an executable and a finite timeout in (0, 60] seconds")
    try:
        check(command, args.transcript, args.timeout)
    except (OSError, ValueError) as error:
        print(f"Synthetic stdio smoke failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
