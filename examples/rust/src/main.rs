//! The smallest Rust bot for `decklogic-bot/1`: read JSON lines, answer each
//! decision with the id of a random offered action. Build it with
//! `cargo build --release` and run it through the host as
//! `ext:path/to/rust-random-bot`.

use serde_json::{json, Value};
use std::io::{BufRead, Write};

fn send(value: Value) {
    let mut out = std::io::stdout().lock();
    let _ = writeln!(out, "{value}");
    let _ = out.flush();
}

fn main() {
    // A xorshift generator seeded from the host's `seed`, so the bot is
    // deterministic. Replace it with your own policy.
    let mut state: u64 = 1;
    for line in std::io::stdin().lock().lines() {
        let Ok(line) = line else { return };
        let Ok(message) = serde_json::from_str::<Value>(&line) else { continue };
        match message["type"].as_str().unwrap_or("") {
            "hello" => send(json!({
                "type": "ready", "protocol": "decklogic-bot/1",
                "name": "rust-random", "version": "1"
            })),
            "game_start" => state = message["seed"].as_u64().unwrap_or(1) | 1,
            "decision" => {
                let count = message["actions"].as_array().map_or(1, Vec::len) as u64;
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                let chosen = message["actions"][(state % count) as usize]["id"].clone();
                send(json!({"type": "action", "n": message["n"], "id": chosen}));
            }
            "bye" => return,
            _ => {}
        }
    }
}
