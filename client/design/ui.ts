// The shared looks, built only from the tokens in tokens.js; components take these instead of spelling classes out.
// Literal class names so Tailwind keeps them.

// Type: what each kind of words looks like wherever it appears.
export const text = {
  display: 'font-serif text-display tracking-[2px] text-fg-default',
  hero: 'font-serif text-hero text-fg-default',
  title: 'font-sans-semibold text-title text-fg-default',
  scene: 'font-serif-body text-body text-fg-default', // narration and story writing
  body: 'font-sans text-body text-fg-default', // what people say, notebook lines
  strong: 'font-sans-semibold text-body text-fg-default', // on buttons and rows
  strongOn: 'font-sans-semibold text-body text-fg-on-emphasis', // the same on an active or picked fill
  label: 'font-sans-semibold text-panel text-fg-default', // on pills
  labelOn: 'font-sans-semibold text-panel text-fg-on-emphasis',
  labelQuiet: 'font-sans-semibold text-panel text-fg-muted',
  tab: 'font-sans-semibold text-chip text-fg-default', // five tabs share 320
  tabOn: 'font-sans-semibold text-chip text-fg-on-emphasis',
  panel: 'font-sans text-panel text-fg-default',
  sub: 'font-sans text-panel text-fg-muted', // the second line of a row
  subOn: 'font-sans text-panel text-fg-on-emphasis opacity-80',
  note: 'font-sans text-chip text-fg-muted', // an intro under a line
  small: 'font-sans text-chip text-fg-default', // a line gathered under another
  head: 'font-sans-semibold text-chip text-fg-muted', // a group's heading
  mono: 'font-mono-medium text-panel text-fg-muted', // the clock
  notice: 'font-sans text-chip italic text-gold-fg', // a notebook notice in the chat
  mark: 'rounded-full bg-gold-muted px-2 font-sans text-chip text-gold-fg', // a mark on a line
} as const;

// Surfaces: a card on the page, a well inside a card, a sheet over the screen.
export const surface = {
  card: 'rounded-xl border border-border-default bg-canvas-default px-3 py-2.5',
  well: 'rounded-xl bg-canvas-subtle px-3 py-2',
  sheet: 'rounded-t-2xl border-x border-t border-border-strong bg-canvas-floating px-4 pb-4 pt-3',
  screen: 'min-h-0 flex-1 gap-4 px-4 py-6',
} as const;

// Controls come in two heights: a pill (36) for many small choices, a button or row (48) for the step to take.
export const control = {
  pill: 'h-9 flex-row items-center justify-center gap-2 rounded-full px-4',
  tab: 'h-9 min-w-0 flex-1 flex-row items-center justify-center gap-1 rounded-full px-1', // a pill that shares a row evenly
  button: 'h-12 flex-row items-center justify-center gap-2 rounded-full px-5',
  row: 'min-h-12 flex-row items-center gap-3 rounded-xl px-4 py-2',
  field: 'h-11 rounded-full border border-border-strong bg-canvas-floating px-4',
} as const;

// Tones: `active` is where you are (the partner, the open tab), `picked` is a choice you made, `idle` and `quiet` any other.
export const tone = {
  idle: 'border border-border-strong',
  active: 'border border-fg-default bg-fg-default',
  picked: 'border border-gold-fg bg-gold-fg',
  offer: 'border border-gold-fg bg-gold-muted',
  quiet: 'border border-border-default bg-canvas-subtle',
  dashed: 'border border-dashed border-border-strong',
} as const;

// Anything that cannot be pressed now looks the same, locked or disabled.
export const off = 'opacity-40';
