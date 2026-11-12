//! Plays one game: `deep` against a bot that takes the first offered action.
//! `cargo run --example play -- <library file> <pack file> [seed]`

use decklogic_simlib_client::{BotSpec, Decision, GameSpec, Library};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let (Some(lib), Some(pack)) = (args.get(1), args.get(2)) else {
        eprintln!("usage: play <library file> <pack file> [seed]");
        std::process::exit(2);
    };
    let seed = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(1);
    let lib = Library::open(lib)?;
    let info = lib.info()?;
    println!("{} on {} (abi {})", info.library, info.engine, info.abi);
    let engine = lib.engine(pack)?;
    let decks = engine.decks()?;
    let mut game = engine.game(&GameSpec::new(
        [decks[0].main.clone(), decks[1].main.clone()],
        seed,
    ))?;
    let mut deep = game.bot(&BotSpec::new("deep", 1, seed))?;
    let mut decisions = 0;
    loop {
        match game.decision()? {
            Decision::Over { result, winner, .. } => {
                println!("{decisions} decisions: {result}, winner {winner:?}");
                return Ok(());
            }
            Decision::Choose { seat: 1, .. } => {
                let id = deep.choose(&mut game)?;
                game.apply(id)?;
            }
            Decision::Choose { actions, .. } => game.apply(actions[0].id)?,
        }
        decisions += 1;
    }
}
