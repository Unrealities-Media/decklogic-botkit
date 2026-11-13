/* Public-owned SDK facade. The generated core header describes required exports.
 * Optional declarations below do not imply availability: dynamically resolve each
 * symbol and check capabilities before use; published v213 lacks both functions.
 */
#ifndef DECKLOGIC_SIMLIB_H
#define DECKLOGIC_SIMLIB_H

#include "decklogic_simlib_core.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * One world the acting seat cannot tell apart from this game, as a new game
 * from the same decision. spec:
 *   {"seed":N,"knowledge":"blind-public-v1","pool":[grp ids]}   (last two optional)
 * The acting seat's view is identical. The opponent's hand, both libraries'
 * order, future shuffles and the seed are sampled from what that seat knows:
 * its own decklist ("blind-public-v1", the default) or, with
 * "format-pool-v1", a pool of grp ids the opponent's deck may hold. Nothing
 * hidden is read from game. Look ahead on samples. NULL on error, including a
 * finished game and the rare decision that cannot be resampled.
 */
DlsGame *dls_game_sample(DlsGame *game, const char *spec);

/*
 * An independent copy of the game in its current state. A copy of a game you
 * play for real knows its hidden cards and future draws, as the original
 * does: copy a dls_game_sample to try actions in one world. NULL on error.
 */
DlsGame *dls_game_clone(const DlsGame *game);


#ifdef __cplusplus
}
#endif
#endif /* DECKLOGIC_SIMLIB_H */
