# Inventory: screens and states from the prototype

`scripts/shoot.mjs` takes one screenshot per screen x viewport x theme and writes `inventory.json`
with each screen's title, headings, buttons, links and fields (accessible names). That list is what the
draft step builds stories from, and the screenshots are what the UX persona compares against.

## Serve the prototype

A folder (exported prototype, Figma Make export, claude.ai artifact saved locally):

```
python -m http.server 4400 --bind 127.0.0.1 -d <prototype folder>
```

(`python3` on macOS, `py -3` on Windows.) A deployed prototype URL works as `baseUrl` directly.

## Playwright

`shoot.mjs` resolves Playwright from the **current directory**, so run it from a folder that has it:
the app repo, or a scratch folder:

```
mkdir ptb-shots && cd ptb-shots && npm init -y && npm i -D playwright && npx playwright install chromium
node <skill>/scripts/shoot.mjs <config.json> <outdir>
```

No Node, or no permission to install it: ask the user for screenshots, use a browser tool you have
(e.g. Claude in Chrome), or Figma frames. Record which screens the shots show in the same `inventory.json`
shape by hand.

## Config

```json
{
  "baseUrl": "http://127.0.0.1:4400/index.html",
  "themeParam": "theme",
  "themeAttribute": "data-theme",
  "viewports": [
    { "name": "desktop", "width": 1440, "height": 900 },
    { "name": "phone", "width": 390, "height": 844 }
  ],
  "themes": ["light", "dark"],
  "waitMs": 1500,
  "startWaitMs": 3000,
  "screens": [
    { "name": "start" },
    { "name": "tools", "click": ["Verktyg"] },
    { "name": "tools-search-empty", "click": ["Verktyg", "Visa filter"], "note": "empty state after filtering" },
    { "name": "news", "path": "/news", "fullPage": true }
  ]
}
```

- `path`: a URL route relative to `baseUrl`.
- `click`: accessible names clicked in order from the start page (link, button, tab or menu item,
  whole-name match, case-insensitive). Use this for prototypes with an in-memory router and **no URL
  routes**. Each screen starts from a fresh page, so click paths never depend on each other.
- States (empty, error, open menu, dialog) are screens too: a click path that ends in that state.
- Themes: `colorScheme` is always set; `themeParam` adds `?theme=dark`, `themeAttribute` sets
  `<html data-theme="dark">`. Use whichever the prototype reads.
- The pointer is moved off the page before each shot so hover flyouts don't cover it.

Files: `<screen>-<viewport>-<theme>.png`. Exit 1 when any shot failed (listed in `failures`).

## When a repo is given

After the shots, compare the inventory with the code (an Explore agent, read-only): which screens and
states have a route/component already, which are partial, which are missing. The gaps become stories;
what exists becomes a note on the story ("reuse `ToolTile`"), not a new story.
