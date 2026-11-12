/* The simulator library from plain C: one game between two built-in bots.
 *
 *   cc -std=c99 -I../include play.c \
 *      -L<dir with the library> -ldecklogic_simlib -o play
 *   LD_LIBRARY_PATH=<dir> ./play sim_TRK.json.gz deep quick 7
 *
 * A real bot parses the decision JSON with a JSON library; this example only
 * needs the deck lists and the end of the game, so it reads those by hand. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "decklogic_simlib.h"

/* Copies the `n`th deck's "main" array (as JSON text, brackets included) out
 * of dls_engine_decks' output into `out`. Returns 0, or -1 if there is none. */
static int nth_deck(const char *decks, int n, char *out, size_t cap) {
    const char *p = decks;
    for (int i = 0; i <= n; i++) {
        p = strstr(p, "\"main\":[");
        if (!p) return -1;
        p += strlen("\"main\":");
    }
    const char *end = strchr(p, ']');
    if (!end || (size_t)(end - p + 2) > cap) return -1;
    memcpy(out, p, (size_t)(end - p + 1));
    out[end - p + 1] = '\0';
    return 0;
}

static int fail(const char *what) {
    fprintf(stderr, "%s: %s\n", what, dls_last_error());
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 5) {
        fprintf(stderr, "usage: %s PACK BOT_A BOT_B SEED\n", argv[0]);
        return 2;
    }
    printf("%s\n", dls_info());
    DlsEngine *engine = dls_engine_open(argv[1]);
    if (!engine) return fail("dls_engine_open");

    static char a[16384], b[16384], spec[40000];
    const char *decks = dls_engine_decks(engine);
    if (nth_deck(decks, 0, a, sizeof a) || nth_deck(decks, 1, b, sizeof b)) {
        fprintf(stderr, "the pack needs two decks\n");
        return 1;
    }
    snprintf(spec, sizeof spec, "{\"decks\":[%s,%s],\"seed\":%s,\"labels\":false}", a, b, argv[4]);
    DlsGame *game = dls_game_new(engine, spec);
    if (!game) return fail("dls_game_new");

    DlsBot *bots[2];
    for (int seat = 0; seat < 2; seat++) {
        char bot_spec[256];
        snprintf(bot_spec, sizeof bot_spec, "{\"bot\":\"%s\",\"seat\":%d,\"seed\":%s}", argv[2 + seat], seat, argv[4]);
        bots[seat] = dls_bot_new(game, bot_spec);
        if (!bots[seat]) return fail("dls_bot_new");
        printf("seat %d: %s\n", seat, dls_bot_version(bots[seat]));
    }

    long decisions = 0;
    for (;;) {
        int32_t seat = dls_game_seat(game);
        if (seat < 0) break; /* no decision outstanding: the game is over */
        int64_t id = dls_bot_choose(bots[seat], game);
        if (id < 0) return fail("dls_bot_choose");
        if (dls_game_apply(game, (uint32_t)id) != 0) return fail("dls_game_apply");
        decisions++;
    }
    printf("%ld decisions\n%s\n", decisions, dls_game_decision(game));

    dls_bot_free(bots[0]);
    dls_bot_free(bots[1]);
    dls_game_free(game);
    dls_engine_free(engine);
    return 0;
}
