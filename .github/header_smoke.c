/* Compile as both C and C++; no optional implementation is linked or called. */
#include "decklogic_simlib.h"
#include "decklogic_simlib_core.h"
#include "decklogic_simlib.h"

const char *(*sdk_info)(void) = dls_info;
DlsGame *(*sdk_sample)(DlsGame *, const char *) = dls_game_sample;
DlsGame *(*sdk_clone)(const DlsGame *) = dls_game_clone;

int main(void) { return !(sdk_info && sdk_sample && sdk_clone); }
