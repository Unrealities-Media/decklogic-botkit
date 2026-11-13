//! A safe Rust wrapper over the DeckLogic simulator shared library,
//! `decklogic-simlib/1`.
//!
//! The library is loaded at run time from a path you give, so this crate
//! builds with no simulator source and no link step. Every decision is the bot
//! protocol's JSON (`decklogic-bot/1`, see `PROTOCOL.md`): the same
//! `observation`, `question` and `actions` a stdio bot is sent.
//!
//! ```no_run
//! use decklogic_simlib_client::{BotSpec, Decision, GameSpec, Library};
//!
//! let lib = Library::open("./libdecklogic_simlib.so")?;
//! let engine = lib.engine("sim_TRK.json.gz")?;
//! let decks = engine.decks()?;
//! let mut game = engine.game(&GameSpec::new([decks[0].main.clone(), decks[1].main.clone()], 7))?;
//! let mut deep = game.bot(&BotSpec::new("deep", 1, 7))?;
//! loop {
//!     match game.decision()? {
//!         Decision::Over { result, winner, .. } => { println!("{result} {winner:?}"); break; }
//!         Decision::Choose { seat: 1, .. } => { let id = deep.choose(&mut game)?; game.apply(id)?; }
//!         Decision::Choose { actions, .. } => game.apply(actions[0].id)?,
//!     }
//! }
//! # Ok::<(), decklogic_simlib_client::Error>(())
//! ```

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::ffi::{c_char, CStr, CString};
use std::path::Path;
use std::sync::Arc;

/// The interface version this wrapper speaks.
pub const LIBRARY: &str = "decklogic-simlib/1";

/// The library's file name on this platform.
pub const FILE_NAME: &str = if cfg!(target_os = "windows") {
    "decklogic_simlib.dll"
} else if cfg!(target_os = "macos") {
    "libdecklogic_simlib.dylib"
} else {
    "libdecklogic_simlib.so"
};

#[derive(Debug)]
pub enum Error {
    /// The library could not be loaded, or lacks a function.
    Load(String),
    /// The library refused a call; the text is its `dls_last_error`.
    Call(String),
    /// A message was not the JSON this wrapper expects.
    Json(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Load(m) => write!(f, "loading the simulator library: {m}"),
            Error::Call(m) => write!(f, "simulator: {m}"),
            Error::Json(m) => write!(f, "simulator message: {m}"),
        }
    }
}

impl std::error::Error for Error {}

pub type Result<T> = std::result::Result<T, Error>;

type Raw = *mut std::ffi::c_void;

struct Fns {
    info: unsafe extern "C" fn() -> *const c_char,
    last_error: unsafe extern "C" fn() -> *const c_char,
    engine_open: unsafe extern "C" fn(*const c_char) -> Raw,
    engine_cards: unsafe extern "C" fn(Raw) -> *const c_char,
    engine_decks: unsafe extern "C" fn(Raw) -> *const c_char,
    engine_free: unsafe extern "C" fn(Raw),
    game_new: unsafe extern "C" fn(Raw, *const c_char) -> Raw,
    game_decision: unsafe extern "C" fn(Raw) -> *const c_char,
    game_seat: unsafe extern "C" fn(Raw) -> i32,
    game_apply: unsafe extern "C" fn(Raw, u32) -> i32,
    game_free: unsafe extern "C" fn(Raw),
    bot_new: unsafe extern "C" fn(Raw, *const c_char) -> Raw,
    bot_choose: unsafe extern "C" fn(Raw, Raw) -> i64,
    bot_version: unsafe extern "C" fn(Raw) -> *const c_char,
    bot_free: unsafe extern "C" fn(Raw),
    // Added after the first release: `None` in a library that predates them.
    game_sample: Option<unsafe extern "C" fn(Raw, *const c_char) -> Raw>,
    game_clone: Option<unsafe extern "C" fn(Raw) -> Raw>,
}

/// The loaded library. Cheap to clone; engines, games and bots keep it loaded.
#[derive(Clone)]
pub struct Library {
    inner: Arc<Loaded>,
}

struct Loaded {
    fns: Fns,
    // Kept last so the functions above are never called after unloading.
    _lib: libloading::Library,
}

/// `dls_info`: the versions of the library you loaded.
#[derive(Clone, Debug, Deserialize)]
pub struct Info {
    pub library: String,
    pub protocol: String,
    pub engine: String,
    pub abi: u32,
}

/// A deck the pack ships.
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Deck {
    #[serde(default)]
    pub label: String,
    pub main: Vec<u32>,
}

/// `dls_game_new`'s spec.
#[derive(Clone, Debug, Serialize)]
pub struct GameSpec {
    pub decks: [Vec<u32>; 2],
    pub seed: u64,
    pub on_play: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deal_model: Option<String>,
    /// Leave each action's human-readable label out (faster).
    pub labels: bool,
}

impl GameSpec {
    pub fn new(decks: [Vec<u32>; 2], seed: u64) -> GameSpec {
        GameSpec {
            decks,
            seed,
            on_play: 0,
            deal_model: None,
            labels: true,
        }
    }
}

/// `dls_game_sample`'s spec.
#[derive(Clone, Debug, Serialize)]
pub struct SampleSpec {
    pub seed: u64,
    /// `blind-public-v1` (the default: the acting seat knows only its own
    /// decklist) or `format-pool-v1` (the opponent's cards come from `pool`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub knowledge: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pool: Option<Vec<u32>>,
}

impl SampleSpec {
    pub fn new(seed: u64) -> SampleSpec {
        SampleSpec {
            seed,
            knowledge: None,
            pool: None,
        }
    }

    /// The opponent's cards come from `pool` (grp ids, with repeats for copies).
    pub fn pool(mut self, pool: Vec<u32>) -> SampleSpec {
        self.knowledge = Some("format-pool-v1".into());
        self.pool = Some(pool);
        self
    }
}

/// `dls_bot_new`'s spec.
#[derive(Clone, Debug, Serialize)]
pub struct BotSpec {
    /// `random`, `beginner`, `quick`, `deep`, or an engine player label.
    pub bot: String,
    pub seat: u8,
    pub seed: u64,
    /// Engine player labels only: `blind-public-v1` or `format-pool-v1`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub knowledge: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pool: Option<Vec<u32>>,
}

impl BotSpec {
    pub fn new(bot: &str, seat: u8, seed: u64) -> BotSpec {
        BotSpec {
            bot: bot.into(),
            seat,
            seed,
            knowledge: None,
            pool: None,
        }
    }
}

/// One offered action.
#[derive(Clone, Debug, Deserialize)]
pub struct ActionEntry {
    pub id: u32,
    /// The engine action, `{"action":"<kind>", ...}`.
    pub action: Value,
    #[serde(default)]
    pub label: Option<String>,
}

/// The outstanding decision, or the end of the game.
#[derive(Clone, Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Decision {
    Choose {
        n: u32,
        seat: u8,
        observation: Value,
        question: Value,
        actions: Vec<ActionEntry>,
    },
    Over {
        result: String,
        winner: Option<u8>,
        #[serde(default)]
        outcome: Value,
    },
}

#[derive(Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum Wire {
    Decision {
        n: u32,
        seat: u8,
        observation: Value,
        question: Value,
        actions: Vec<ActionEntry>,
    },
    Over {
        result: String,
        winner: Option<u8>,
        #[serde(default)]
        outcome: Value,
    },
}

impl Library {
    /// Loads the library at `path` and checks it speaks `decklogic-simlib/1`.
    pub fn open(path: impl AsRef<Path>) -> Result<Library> {
        // SAFETY: loading runs the library's initialisers; this is the
        // DeckLogic simulator library, which has none beyond Rust's own.
        let lib = unsafe { libloading::Library::new(path.as_ref()) }
            .map_err(|e| Error::Load(format!("{}: {e}", path.as_ref().display())))?;
        macro_rules! sym {
            ($name:literal) => {
                // SAFETY: each symbol's type is the header's declaration.
                *unsafe { lib.get(concat!($name, "\0").as_bytes()) }
                    .map_err(|e| Error::Load(format!("{}: {e}", $name)))?
            };
        }
        let fns = Fns {
            info: sym!("dls_info"),
            last_error: sym!("dls_last_error"),
            engine_open: sym!("dls_engine_open"),
            engine_cards: sym!("dls_engine_cards"),
            engine_decks: sym!("dls_engine_decks"),
            engine_free: sym!("dls_engine_free"),
            game_new: sym!("dls_game_new"),
            game_decision: sym!("dls_game_decision"),
            game_seat: sym!("dls_game_seat"),
            game_apply: sym!("dls_game_apply"),
            game_free: sym!("dls_game_free"),
            bot_new: sym!("dls_bot_new"),
            bot_choose: sym!("dls_bot_choose"),
            bot_version: sym!("dls_bot_version"),
            bot_free: sym!("dls_bot_free"),
            // SAFETY: each symbol's type is the header's declaration.
            game_sample: unsafe { lib.get(b"dls_game_sample\0") }.ok().map(|f| *f),
            game_clone: unsafe { lib.get(b"dls_game_clone\0") }.ok().map(|f| *f),
        };
        let library = Library {
            inner: Arc::new(Loaded { fns, _lib: lib }),
        };
        let info = library.info()?;
        if info.library != LIBRARY {
            return Err(Error::Load(format!(
                "the library speaks {}, this wrapper {LIBRARY}",
                info.library
            )));
        }
        Ok(library)
    }

    /// Loads [`FILE_NAME`] from the directory in `DECKLOGIC_SIMLIB_DIR`, or
    /// the file `DECKLOGIC_SIMLIB` names.
    pub fn from_env() -> Result<Library> {
        if let Ok(file) = std::env::var("DECKLOGIC_SIMLIB") {
            return Library::open(file);
        }
        let dir = std::env::var("DECKLOGIC_SIMLIB_DIR").unwrap_or_else(|_| ".".into());
        Library::open(Path::new(&dir).join(FILE_NAME))
    }

    fn f(&self) -> &Fns {
        &self.inner.fns
    }

    /// The library's versions, including the engine stamp it was built from.
    pub fn info(&self) -> Result<Info> {
        let text = self.text(unsafe { (self.f().info)() })?;
        serde_json::from_str(&text).map_err(|e| Error::Json(e.to_string()))
    }

    fn error(&self) -> Error {
        let p = unsafe { (self.f().last_error)() };
        if p.is_null() {
            return Error::Call("unknown error".into());
        }
        Error::Call(unsafe { CStr::from_ptr(p) }.to_string_lossy().into_owned())
    }

    fn text(&self, p: *const c_char) -> Result<String> {
        if p.is_null() {
            return Err(self.error());
        }
        Ok(unsafe { CStr::from_ptr(p) }.to_string_lossy().into_owned())
    }

    /// Loads a pack (`.json` or `.json.gz`).
    pub fn engine(&self, pack: impl AsRef<Path>) -> Result<Engine> {
        let path = CString::new(pack.as_ref().to_string_lossy().as_bytes())
            .map_err(|e| Error::Call(e.to_string()))?;
        let raw = unsafe { (self.f().engine_open)(path.as_ptr()) };
        if raw.is_null() {
            return Err(self.error());
        }
        Ok(Engine {
            lib: self.clone(),
            raw,
        })
    }
}

/// A loaded pack. Games may outlive it. Shareable across threads.
pub struct Engine {
    lib: Library,
    raw: Raw,
}

// SAFETY: the library documents an engine as shareable between threads.
unsafe impl Send for Engine {}
unsafe impl Sync for Engine {}

impl Engine {
    /// The pack's card sheet (`decklogic-cards/1`).
    pub fn cards(&self) -> Result<Value> {
        let text = self
            .lib
            .text(unsafe { (self.lib.f().engine_cards)(self.raw) })?;
        serde_json::from_str(&text).map_err(|e| Error::Json(e.to_string()))
    }

    /// The decks the pack ships.
    pub fn decks(&self) -> Result<Vec<Deck>> {
        let text = self
            .lib
            .text(unsafe { (self.lib.f().engine_decks)(self.raw) })?;
        serde_json::from_str(&text).map_err(|e| Error::Json(e.to_string()))
    }

    pub fn game(&self, spec: &GameSpec) -> Result<Game> {
        let spec =
            CString::new(serde_json::to_string(spec).map_err(|e| Error::Json(e.to_string()))?)
                .map_err(|e| Error::Call(e.to_string()))?;
        let raw = unsafe { (self.lib.f().game_new)(self.raw, spec.as_ptr()) };
        if raw.is_null() {
            return Err(self.lib.error());
        }
        Ok(Game {
            lib: self.lib.clone(),
            raw,
        })
    }
}

impl Drop for Engine {
    fn drop(&mut self) {
        unsafe { (self.lib.f().engine_free)(self.raw) }
    }
}

/// One game. Use it from one thread at a time (it is `Send`, not `Sync`).
pub struct Game {
    lib: Library,
    raw: Raw,
}

// SAFETY: a game may move between threads; `&mut self` keeps one user at a time.
unsafe impl Send for Game {}

impl Game {
    /// The outstanding decision as the library's JSON text.
    pub fn decision_text(&mut self) -> Result<String> {
        self.lib
            .text(unsafe { (self.lib.f().game_decision)(self.raw) })
    }

    /// The outstanding decision, parsed.
    pub fn decision(&mut self) -> Result<Decision> {
        let text = self.decision_text()?;
        let wire: Wire = serde_json::from_str(&text).map_err(|e| Error::Json(e.to_string()))?;
        Ok(match wire {
            Wire::Decision {
                n,
                seat,
                observation,
                question,
                actions,
            } => Decision::Choose {
                n,
                seat,
                observation,
                question,
                actions,
            },
            Wire::Over {
                result,
                winner,
                outcome,
            } => Decision::Over {
                result,
                winner,
                outcome,
            },
        })
    }

    /// The seat to act, or `None` once the game is over.
    pub fn seat(&mut self) -> Option<u8> {
        let seat = unsafe { (self.lib.f().game_seat)(self.raw) };
        u8::try_from(seat).ok()
    }

    /// Answers the outstanding decision with an offered action id.
    pub fn apply(&mut self, id: u32) -> Result<()> {
        match unsafe { (self.lib.f().game_apply)(self.raw, id) } {
            0 => Ok(()),
            _ => Err(self.lib.error()),
        }
    }

    /// One world the acting seat cannot tell apart from this game, as a new
    /// game from the same decision: its own view is identical, and the
    /// opponent's hand, both libraries and future shuffles are sampled from
    /// what it knows. Look ahead on samples, never on the real game.
    pub fn sample(&mut self, spec: &SampleSpec) -> Result<Game> {
        let f = self
            .lib
            .f()
            .game_sample
            .ok_or_else(|| Error::Load("dls_game_sample: this library predates it".into()))?;
        let spec =
            CString::new(serde_json::to_string(spec).map_err(|e| Error::Json(e.to_string()))?)
                .map_err(|e| Error::Call(e.to_string()))?;
        let raw = unsafe { f(self.raw, spec.as_ptr()) };
        if raw.is_null() {
            return Err(self.lib.error());
        }
        Ok(Game {
            lib: self.lib.clone(),
            raw,
        })
    }

    /// An independent copy in the same state. A copy of a real game knows its
    /// hidden cards and future draws: copy a [`Game::sample`] to look ahead.
    pub fn try_clone(&self) -> Result<Game> {
        let f = self
            .lib
            .f()
            .game_clone
            .ok_or_else(|| Error::Load("dls_game_clone: this library predates it".into()))?;
        let raw = unsafe { f(self.raw) };
        if raw.is_null() {
            return Err(self.lib.error());
        }
        Ok(Game {
            lib: self.lib.clone(),
            raw,
        })
    }

    /// Seats a built-in bot in this game.
    pub fn bot(&self, spec: &BotSpec) -> Result<Bot> {
        let spec =
            CString::new(serde_json::to_string(spec).map_err(|e| Error::Json(e.to_string()))?)
                .map_err(|e| Error::Call(e.to_string()))?;
        let raw = unsafe { (self.lib.f().bot_new)(self.raw, spec.as_ptr()) };
        if raw.is_null() {
            return Err(self.lib.error());
        }
        Ok(Bot {
            lib: self.lib.clone(),
            raw,
        })
    }
}

impl Drop for Game {
    fn drop(&mut self) {
        unsafe { (self.lib.f().game_free)(self.raw) }
    }
}

/// A built-in bot seated in one game.
pub struct Bot {
    lib: Library,
    raw: Raw,
}

// SAFETY: as `Game`.
unsafe impl Send for Bot {}

impl Bot {
    /// The bot's pick for `game`'s outstanding decision, not applied.
    pub fn choose(&mut self, game: &mut Game) -> Result<u32> {
        let id = unsafe { (self.lib.f().bot_choose)(self.raw, game.raw) };
        u32::try_from(id).map_err(|_| self.lib.error())
    }

    /// The bot's versioned label, e.g. `deep-format-v20`.
    pub fn version(&self) -> Result<String> {
        self.lib
            .text(unsafe { (self.lib.f().bot_version)(self.raw) })
    }
}

impl Drop for Bot {
    fn drop(&mut self) {
        unsafe { (self.lib.f().bot_free)(self.raw) }
    }
}
