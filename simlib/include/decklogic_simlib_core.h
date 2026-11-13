/*
 * decklogic_simlib.h: the DeckLogic Limited simulator as a shared library.
 * Interface version "decklogic-simlib/1".
 *
 * Every message is the JSON of the bot protocol, decklogic-bot/1
 * (PROTOCOL.md): a decision carries the same "observation", "question" and
 * "actions" a protocol bot is sent over stdio.
 *
 * Ownership: strings the library returns belong to it. An engine's strings
 * live until the engine is freed; a game's decision string until the next
 * call on that game; dls_info's string forever. Never free them.
 *
 * Errors: functions return NULL or -1 and set a message for the calling
 * thread, read with dls_last_error().
 *
 * Threads: a handle is used by one thread at a time. Games on different
 * threads may share one engine. An engine may be freed while its games live.
 */
#ifndef DECKLOGIC_SIMLIB_CORE_H
#define DECKLOGIC_SIMLIB_CORE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct DlsEngine DlsEngine;
typedef struct DlsGame DlsGame;
typedef struct DlsBot DlsBot;

/* {"library":"decklogic-simlib/1","protocol":"decklogic-bot/1","engine":"sim-engine-vN","abi":N} */
const char *dls_info(void);

/* The calling thread's last error, or NULL. Valid until its next library call. */
const char *dls_last_error(void);

/* Loads a pack (.json or gzip) from a file, or from memory. NULL on error. */
DlsEngine *dls_engine_open(const char *path);
DlsEngine *dls_engine_load(const uint8_t *bytes, size_t len);

/* The pack's card sheet (decklogic-cards/1), as hello.cards carries it. */
const char *dls_engine_cards(const DlsEngine *engine);

/* The decks the pack ships: [{"label":"...","main":[grp ids]}]. */
const char *dls_engine_decks(const DlsEngine *engine);

void dls_engine_free(DlsEngine *engine);

/*
 * Starts a game. spec:
 *   {"decks":[[grp ids],[grp ids]],"seed":N,
 *    "on_play":0, "deal_model":"...", "labels":true}   (last three optional)
 * "labels":false leaves out each action's human-readable label, for speed.
 */
DlsGame *dls_game_new(const DlsEngine *engine, const char *spec);

/*
 * The outstanding decision:
 *   {"type":"decision","n":N,"seat":S,"observation":{...},"question":{...},
 *    "actions":[{"id":0,"label":"...","action":{...}}, ...]}
 * or, once the game has ended:
 *   {"type":"over","result":"win"|"draw"|"capped","winner":S|null,"outcome":{...}}
 */
const char *dls_game_decision(DlsGame *game);

/* The seat to act, 0 or 1; -1 once the game is over or on error. */
int32_t dls_game_seat(DlsGame *game);

/* Answers the outstanding decision with an offered action id. 0, or -1 (game unchanged). */
int32_t dls_game_apply(DlsGame *game, uint32_t id);

void dls_game_free(DlsGame *game);

/*
 * Seats a built-in bot in one game. spec:
 *   {"bot":"deep","seat":1,"seed":7}
 * "bot" is a ladder name (random, beginner, quick, deep) or an engine player
 * label (heuristic-v3, search-v3:96:48, ...); engine labels also take
 * "knowledge" ("blind-public-v1", default, or "format-pool-v1") and "pool"
 * (grp ids; default both decks of the game).
 */
DlsBot *dls_bot_new(const DlsGame *game, const char *spec);

/* The bot's pick for the outstanding decision as an offered id, not applied. -1 on error. */
int64_t dls_bot_choose(DlsBot *bot, DlsGame *game);

/* The bot's versioned label, e.g. "deep-format-v20". Lives as long as the bot. */
const char *dls_bot_version(const DlsBot *bot);

void dls_bot_free(DlsBot *bot);

#ifdef __cplusplus
}
#endif

#endif /* DECKLOGIC_SIMLIB_CORE_H */
