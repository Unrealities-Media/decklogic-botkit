# From training to an importable learned bot

A learned bot is an ordinary protocol client whose decisions depend on model
files. It needs no special registry format and need not copy or beat a built-in
policy. Use the [public library](simlib/README.md) for training and the
[stdio contract](protocol/PROTOCOL.md) for deployment. The original
[DEMO](sample/demo/README.md) needs no private assets.

## Keep one encoder across both routes

Implement an author-owned function that scores each structured offered action
using the acting seat's observation. Reuse that encoder in training and
inference. Version its ordered features/vocabulary, preprocessing and action
selection rule alongside the model. Do not use debug labels, hidden referee
state or unavailable future information as inference features.

Direct `game.decision()` / `game.apply(id)` loops can score all variable-length
candidates and return the selected offered ID. A fixed-width neural head is
optional: the environment adapters' `max_actions` masks can cut candidates, so
record `actions_cut` when using them. Never reinterpret an offered action ID
as a persistent model class; IDs describe the current decision only.

Keep stochastic training separate from deployment behavior. For example,
softmax sampling during learning and deterministic argmax during deployment
are different policies. Evaluate the actual deployment rule on held-out deals
after freezing weights; a legal deterministic policy can still lose every game.
For stochastic deployment, initialize randomness from the protocol seed and
verify replay rather than using time or process entropy.

## Retain the training evidence

Record engine/ABI, library binary hash, pack file and semantic checksums,
ordered decks, opponent version/knowledge, training and held-out seed schedules,
seat/on-play assignments, encoder version, optimizer settings and final model
hash. Preserve enough decisions, rewards and update metadata to check that the
artifact came from the recorded training process. This is provenance, not a
claim of identical floating-point training results on every device.

Distinguish normal terminal results from truncations. Direct-library `over`
messages include `result` and, for wins, `winner`; retain the whole terminal
object, including `outcome.reason` when present. A capped game is not a normal
draw or a win/loss sample. Record trainer-imposed wall/decision caps and mask
cuts too. Use disjoint held-out deal seeds and describe remaining opponent-seed
or seat correlations instead of calling a tiny trial balanced.

## Package inference separately

An example submission layout is:

```text
my-bot/
  manifest.json
  bot.py
  policy.py
  weights.json
  model_identity.json
```

The entry can be `python -B bot.py`. Put required weights, vocabularies and
configuration inside the payload, outside excluded caches such as `target`,
`.venv` and `node_modules`. Resolve assets relative to the source module, for
example `Path(__file__).resolve().parent / "weights.json"`; import and archival
change the submission's parent and absolute path. Training scripts, traces and
reports can stay outside the submitted runtime payload. Inference needs a
simulator library only if the policy actually calls it.

Before emitting `ready`, check model existence, schema, encoder/vocabulary
version, dimensions and finite values. A separate hash pin detects accidental
substitution, but an author can rewrite both files; the registry must hash the
entire reviewed payload. Changed weights or preprocessing require a new bot
version and qualification.

Keep loading errors on stderr and fail clearly. Do not silently substitute an
untrained policy while reporting the trained model's identity. Flush protocol
replies, return only offered IDs, and keep stdout free of training progress or
diagnostic logs. Declare inference runtime dependencies in the manifest; they
remain separate from source-hash attestation.

## Check the handoff before submission

1. Feed the same recorded decision through the training encoder and deployed
   scorer; compare features and actions under the deployment rule.
2. Verify exported weights match the recorded updates or checkpoint. Confirm
   inference actually uses them; an ablation can reveal an ignored model,
   though changed choices do not prove improvement.
3. Launch from a different working directory. Test missing/corrupt weights,
   incompatible schemas and missing runtime components in separate copies.
4. Run public `validate` and inspect every check, fault and cap count. Validation
   measures protocol behavior, latency and replay on a sampled cohort, not strength.
5. Follow the [version-specific registry process](registry/README.md). With the
   next-kit host, import the frozen payload, verify its context, and compare
   against selected opponents with retained settings. Check that changing model
   bytes invalidates the admitted receipt.

Retain exact evaluated bytes and receipts. A Git checkout may convert text,
and a model re-export can change bytes even when its numeric values appear
unchanged. Reproduce with the retained host, pack, cohort and runtime, and
requalify when those requirements change.
