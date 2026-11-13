//! Runs against a built library: set `DECKLOGIC_SIMLIB_DIR` (the directory
//! holding it, e.g. DeckLogic's `target/debug`) or `DECKLOGIC_SIMLIB` (the
//! file), and `DECKLOGIC_SIMLIB_PACK` (a pack file; default the HOB pack of a
//! DeckLogic checkout this crate sits in).

use decklogic_simlib_client::{
    BotSpec, Decision, Error, Game, GameSpec, Library, SampleSpec, LIBRARY,
};

fn library() -> Library {
    assert!(
        std::env::var_os("DECKLOGIC_SIMLIB").is_some()
            || std::env::var_os("DECKLOGIC_SIMLIB_DIR").is_some(),
        "set DECKLOGIC_SIMLIB_DIR to the directory holding the built library"
    );
    Library::from_env().expect("load the library")
}

fn pack() -> String {
    std::env::var("DECKLOGIC_SIMLIB_PACK").unwrap_or_else(|_| {
        format!(
            "{}/../../../etl/sim/sim_HOB.json.gz",
            env!("CARGO_MANIFEST_DIR")
        )
    })
}

#[test]
fn plays_a_game_to_the_end_and_repeats_it() {
    let lib = library();
    assert_eq!(lib.info().unwrap().library, LIBRARY);
    let engine = lib.engine(pack()).unwrap();
    assert_eq!(engine.cards().unwrap()["format"], "decklogic-cards/1");
    let decks = engine.decks().unwrap();
    let run = |seed: u64| {
        let mut spec = GameSpec::new([decks[0].main.clone(), decks[1].main.clone()], seed);
        spec.labels = false;
        let mut game = engine.game(&spec).unwrap();
        let mut bots = [0u8, 1].map(|seat| game.bot(&BotSpec::new("random", seat, seed)).unwrap());
        let mut ids = Vec::new();
        loop {
            match game.decision().unwrap() {
                Decision::Over { result, .. } => return (ids, result),
                Decision::Choose { seat, actions, .. } => {
                    assert!(actions[0].label.is_none());
                    assert_eq!(game.seat(), Some(seat));
                    let id = bots[seat as usize].choose(&mut game).unwrap();
                    game.apply(id).unwrap();
                    ids.push(id);
                }
            }
        }
    };
    let first = run(5);
    assert!(first.0.len() > 20);
    assert_eq!(first, run(5));
}

#[test]
fn errors_carry_the_library_message() {
    let lib = library();
    match lib.engine("/no/such/pack.json") {
        Err(Error::Call(message)) => assert!(message.contains("/no/such/pack.json")),
        Err(other) => panic!("{other}"),
        Ok(_) => panic!("a missing pack loaded"),
    }
    let engine = lib.engine(pack()).unwrap();
    let decks = engine.decks().unwrap();
    let mut game = engine
        .game(&GameSpec::new(
            [decks[0].main.clone(), decks[1].main.clone()],
            1,
        ))
        .unwrap();
    assert!(matches!(game.apply(9_999), Err(Error::Call(m)) if m.contains("not offered")));
    assert!(game.bot(&BotSpec::new("grandmaster", 0, 1)).is_err());
}

#[test]
fn bots_refuse_a_different_game() {
    let lib = library();
    let engine = lib.engine(pack()).unwrap();
    let decks = engine.decks().unwrap();
    let spec = GameSpec::new([decks[0].main.clone(), decks[1].main.clone()], 1);
    let mut original = engine.game(&spec).unwrap();
    let mut other = engine.game(&spec).unwrap();
    let seat = original.seat().unwrap();
    let mut bot = original.bot(&BotSpec::new("random", seat, 1)).unwrap();
    let wrong_game = bot.choose(&mut other);
    assert!(
        matches!(&wrong_game, Err(Error::Call(m)) if m.contains("different game")),
        "{wrong_game:?}"
    );
    assert!(bot.choose(&mut original).is_ok());
    let separately_loaded = library();
    let separate_engine = separately_loaded.engine(pack()).unwrap();
    let mut separate_game = separate_engine.game(&spec).unwrap();
    assert!(
        matches!(bot.choose(&mut separate_game), Err(Error::Call(m)) if m.contains("different game"))
    );
    drop(original);
    let mut later = engine.game(&spec).unwrap();
    assert!(matches!(bot.choose(&mut later), Err(Error::Call(m)) if m.contains("different game")));
}

#[test]
fn a_game_outlives_its_engine_and_moves_threads() {
    let lib = library();
    let engine = lib.engine(pack()).unwrap();
    let decks = engine.decks().unwrap();
    let mut game = engine
        .game(&GameSpec::new(
            [decks[0].main.clone(), decks[1].main.clone()],
            2,
        ))
        .unwrap();
    drop(engine);
    std::thread::spawn(move || {
        for _ in 0..20 {
            if game.seat().is_none() {
                break;
            }
            game.apply(0).unwrap();
        }
    })
    .join()
    .unwrap();
}

#[test]
fn samples_and_copies_play_on_from_the_same_decision() {
    let lib = library();
    let engine = lib.engine(pack()).unwrap();
    let decks = engine.decks().unwrap();
    let mut game = engine
        .game(&GameSpec::new(
            [decks[0].main.clone(), decks[1].main.clone()],
            3,
        ))
        .unwrap();
    let mut bots = [0u8, 1].map(|seat| game.bot(&BotSpec::new("random", seat, 3)).unwrap());
    for _ in 0..30 {
        let seat = game.seat().unwrap();
        let id = bots[seat as usize].choose(&mut game).unwrap();
        game.apply(id).unwrap();
    }
    let view = |g: &mut Game| match g.decision().unwrap() {
        Decision::Choose {
            observation,
            question,
            actions,
            ..
        } => serde_json::to_string(&(observation, question, actions.len())).unwrap(),
        Decision::Over { .. } => panic!("over"),
    };
    let here = view(&mut game);
    let mut copy = match game.try_clone() {
        Err(Error::Load(why)) => return eprintln!("skipped: {why}"),
        copy => copy.unwrap(),
    };
    assert_eq!(view(&mut copy), here);
    let mut world = game.sample(&SampleSpec::new(9)).unwrap();
    assert_eq!(view(&mut world), here);
    world.apply(0).unwrap();
    assert_eq!(view(&mut game), here, "the real game is untouched");
    let refused = game.sample(&SampleSpec {
        knowledge: Some("open-hand".into()),
        ..SampleSpec::new(1)
    });
    assert!(matches!(refused, Err(Error::Call(m)) if m.contains("knowledge")));
}
