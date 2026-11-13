# Observation fields: combat values and identity

These fields describe a visible object in `observation.hand`, `board`,
`revealed` or `decision_objects`. They are live values for the current
decision, not the printed card-sheet values. Use the structured offered
actions for legality; these fields help evaluate those actions.

| Field | Meaning |
|---|---|
| `power`, `toughness` | Signed integers computed by the engine for the current object. They already include its applicable base-value changes, +1/+1 and -1/-1 counters, temporary P/T changes, and modeled continuous bonuses such as anthems and attachment buffs. Do **not** add counters or buffs again. Toughness is **not** reduced by marked damage. Check `is_creature` when evaluating a creature; an object's numeric P/T fields alone do not establish its current type |
| `damage` | Damage currently marked on this object, separate from toughness. This is not total lifetime damage, power lost, or “remaining health.” Marked damage is cleared at cleanup and on zone changes. Prevention/replacement effects may affect how much damage gets marked |
| `blocking` | The object-instance `id` of the attacker this object is currently blocking, or `null` when it is not blocking. It is not a `grp_id`, seat number, Boolean, or list of creatures blocking this object. Several blockers can point to the same attacker; inspect their rows to find them |
| `board_age` | Nonnegative count of engine turn-counter increments since this battlefield arrival: 0 on the arrival turn, 1 after the next turn begins, and so on. It counts both players' turns, not full rounds or controller turns. `null` outside the battlefield. It is not an absolute entry turn and does not by itself establish summoning sickness; use `summoning_sick` |

For example, a printed 3/3 with one +1/+1 counter and a temporary +2/+2 bonus
has `power: 6`, `toughness: 6`, `plus_counters: 1`. If it has two marked
damage, `damage: 2`; toughness remains 6. A simple estimate of additional
ordinary damage needed to reach lethal damage is `toughness - damage`, not
another adjustment to the observed toughness. This is not a complete combat
rule: deathtouch, indestructible, prevention, first/double strike and other
effects can change the outcome. Choose from the offered legal actions.

`plus_counters` and `minus_counters` expose counters as counters, so a bot can
distinguish durable growth from a temporary bonus without double-counting
their current effect. Other named counters may appear in optional `counters`.
An absent optional field is not permission to infer private information.

Use object `id` to follow references within the current game. `grp_id`
identifies a card definition/printing (invented local ids in the synthetic
demo), so multiple objects can share it. If a referenced object is not in the
visible lists, handle that lookup safely rather than inventing its attributes.
