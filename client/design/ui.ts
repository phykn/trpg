// Components take these looks instead of spelling classes out; tailwind-merge lets the last of two fighting classes win.
// Literal class names so Tailwind keeps them.
import { cva, cx } from 'class-variance-authority';
import { extendTailwindMerge } from 'tailwind-merge';

import { fontSize } from './tokens';

// Our text sizes have their own names; tell tailwind-merge they are sizes, not colors.
const merge = extendTailwindMerge({ extend: { classGroups: { 'font-size': [{ text: Object.keys(fontSize) }] } } });

type ClassValue = Parameters<typeof cx>[number];

export const cn = (...classes: ClassValue[]) => merge(cx(classes));

const withMerge = <P>(look: (props?: P) => string) => (props?: P, ...extra: ClassValue[]) => cn(look(props), extra);

// Type: what each kind of words looks like wherever it appears. `on` is the same words on an active or picked fill.
export const text = withMerge(cva('text-fg-default', {
  variants: {
    kind: {
      display: 'font-serif text-display tracking-[2px]',
      hero: 'font-serif text-hero',
      title: 'font-sans-semibold text-title',
      scene: 'font-serif-body text-body', // narration and story writing
      body: 'font-sans text-body', // what people say, notebook lines
      input: 'font-sans text-input', // what the player types
      strong: 'font-sans-semibold text-body', // on buttons and rows
      label: 'font-sans-semibold text-panel', // on pills
      tab: 'font-sans-semibold text-chip', // five tabs share 320
      panel: 'font-sans text-panel',
      sub: 'font-sans text-panel text-fg-muted', // the second line of a row
      note: 'font-sans text-chip text-fg-muted', // an intro under a line
      small: 'font-sans text-chip', // a line gathered under another
      head: 'font-sans-semibold text-chip text-fg-muted', // a group's heading
      mono: 'font-mono-medium text-panel text-fg-muted', // the clock
      // The top bar's clock, turns and notebook count: one face for Hangul and digits alike, so none looks bigger.
      bar: 'font-sans-semibold text-body text-fg-muted',
      value: 'w-9 text-center font-mono-medium text-title', // a number set with steppers
      total: 'font-mono-medium text-title', // what a roll came to
      // The number a roll has to reach, ringed: in the chat line and, larger, on the dice sheet.
      need: 'rounded-full border border-border-strong px-2 font-sans-semibold text-chip text-fg-muted',
      notice: 'font-sans text-chip italic text-gold-fg', // a notebook notice in the chat
      mark: 'rounded-full bg-gold-muted px-2 font-sans text-chip text-gold-fg', // a mark on a line
      topic: 'font-sans text-body text-topic-fg underline', // a topic named in what a person says
    },
    on: { true: 'text-fg-on-emphasis' },
    quiet: { true: 'text-fg-muted' },
  },
  compoundVariants: [{ kind: 'sub', on: true, class: 'opacity-80' }],
  defaultVariants: { kind: 'body' },
}));

// Surfaces: a card on the page, a well inside a card, a whole screen.
export const surface = withMerge(cva('', {
  variants: {
    kind: {
      card: 'rounded-xl border border-border-default bg-canvas-default px-3 py-2.5',
      well: 'rounded-xl bg-canvas-subtle px-3 py-2',
      float: 'gap-2.5 rounded-xl border border-border-default bg-canvas-floating p-3 shadow-lg', // a card over the page
      screen: 'min-h-0 flex-1 gap-4 px-4 py-6',
    },
  },
}));

// Controls come in two heights: a pill or tab (36) for many small choices, a button or row (48) for the step to take.
// Tones: `active` is where you are (the partner, the open tab), `picked` is a choice you made, `idle` and `quiet` any other.
// Anything that cannot be pressed now looks the same, locked or disabled.
export const control = withMerge(cva('flex-row items-center', {
  variants: {
    kind: {
      pill: 'h-9 justify-center gap-2 rounded-full px-4',
      tab: 'h-9 min-w-0 flex-1 justify-center gap-1 rounded-full px-1', // shares a row evenly
      // An icon over its word, sharing a row evenly: the notebook's groups.
      segment: 'h-12 min-w-0 flex-1 flex-col justify-center gap-0.5 rounded-xl px-1',
      icon: 'h-10 w-10 justify-center rounded-full', // an icon alone: the notebook, settings
      step: 'h-9 w-9 justify-center rounded-xl', // a triangle that steps a number up or down
      button: 'h-12 justify-center gap-2 rounded-full px-5',
      row: 'min-h-12 gap-3 rounded-xl px-4 py-2',
      // The chat box: the words and the send button inside one rounded box that grows with the words.
      composer: 'items-end rounded-2xl border-2 border-border-default bg-canvas-floating',
    },
    tone: {
      idle: 'border border-border-strong',
      active: 'border border-fg-default bg-fg-default',
      picked: 'border border-gold-fg bg-gold-fg',
      offer: 'border border-gold-fg bg-gold-muted',
      quiet: 'border border-border-default bg-canvas-subtle',
      dashed: 'border border-dashed border-border-strong',
      focus: 'border-gold-fg',
      plain: '', // no border or fill: a step, a menu entry on its card
      raised: 'bg-canvas-floating shadow-sm', // the open segment
    },
    off: { true: 'opacity-40' },
  },
  defaultVariants: { tone: 'idle' },
}));
