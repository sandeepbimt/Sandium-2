# Compact menu after #1221 feedback

Inspected supplied screenshots155950 (editor),155958 (loaded page),155959
(homepage). Large vertical blank space remained because every tile reserved a
separate48dp state button plus28dp editor overlay clearance. The editor also
showed the immutable library row and placed Reset below available actions.

## Layout

* Keep26dp icons,12sp neutral labels, shared baselines and two label lines.
  Remove the universal state-button reservation and edit-overlay clearance.
  Nominal normal-font tile is64dp; regular sheet328dp versus538dp previously,
  about39% shorter. Actual metrics follow system font scaling.
* Regular height still depends only on window/font configuration, not loaded
  page, live action count, selected quick page or All menu directory. Width stays
  window-derived. Smaller displays/large fonts scroll rather than clip content.
* Editor is48dp taller than regular (nominal376dp), omits the fixed noneditable
  library row and puts Reset between Cancel/Done. It fits the quick grid, hint,
  pager, Available heading and one row of hidden actions at normal font size.
  More hidden actions or constrained/accessibility windows retain scrolling.
* Pagers use20dp marks with8dp gaps in all page counts; no special two-page rule.
  A single minimum48dp-wide/high accessible range widget offers forward/back
  actions and left/right keyboard control. Marks are not tiny TalkBack buttons.
  Direct taps/swipes and drag-hover page switching remain available.

## Interactions and state

* All menu is always projected last, independent of its saved legacy position,
  hidden flag or current-page catalog. It cannot move/remove in edit. User action
  ordering/hidden state is preserved, including temporarily unavailable actions.
* Compact editor uses a full-tile target:tap for Add/Remove/Move options;
  long-press for direct drag. Visible hint and accessible names describe this.
  This replaces separate corner plus/minus buttons, avoiding overlap with icons
  in shorter tiles. Completed edits still persist; Cancel restores entry state.
* Checkable rows such as Desktop use the whole tile as their toggle target,
  retaining the existing native child click handler and live enabled/checked
  guards. Title and On/Off remain separate single lines. Editor never toggles it.
* Non-toggle compound actions open the original native row so no secondary
  operation is lost. Other native dispatch and managed state stay unchanged.

## Verification

New tests check compact geometry budget, accessible pager, editor/toggle dispatch,
plus real-JVM trailing projection across catalog changes, hide/re-add, move,
legacy positions, serialization/reload and dropping onto the fixed last tile.
No CI run/publication here. Android compilation and device visual verification
remain for the user's next authorized run.

Validation completed:active298, Full49 and legacy19 passed; motion6 and theme18
passed. Independent source/API review found no blocking issue. The compactness
percentage is a nominal geometry estimate, not a measured APK result.
