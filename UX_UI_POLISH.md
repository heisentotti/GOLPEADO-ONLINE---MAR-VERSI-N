# Golpeado Online — UX/UI Polish Final

## Scope
Final desktop polish over the existing engine, bot and online architecture. No game rules or authoritative state logic were changed.

## UX changes
- Felt-inspired dark green table with restrained ivory/brass card palette.
- Redesigned physical cards with rank/suit hierarchy and selected state.
- Hover/lift feedback on cards without expensive effects.
- Strong current-turn and phase indicators.
- Public opponent panels show only name, card count and lowered group.
- Private enchufe is represented only as `PRIVADO` / `NINGUNO`.
- Clear deck/discard/table status panels.
- Action bar emphasizes only currently useful actions.
- Illegal/invalid actions are disabled or ignored visually; `Game` remains the authority.
- Keyboard shortcuts: Space (obtain), D (discard), R (sort), Esc (clear selection).
- Victory uses an in-game overlay instead of a blocking system dialog.
- Menu spacing, typography and contrast were tightened for desktop readability.
- Layout uses expanding frames and minimum window sizing for resizing behavior.
- Effects are lightweight: no continuous canvas animation, image filters or high-frequency loops.

## Rule-preserving UI detail
After a player has obtained a card, `RECOGER DESCARTE` is no longer offered in the action phase. The UI therefore reflects the official rule that drawing from the deck and taking the last discard are alternatives, never two actions in one turn.

## Verification
- `python -m compileall -q golpeado`
- `xvfb-run -a pytest -q`
- Full suite: 96 passed
