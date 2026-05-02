import React from 'react';

// Two-mode expand state. Historically a single hook switched between
// "shared via context" and "isolated local" depending on whether a
// provider was present, which made caller intent invisible. Split:
// `useExpandGroup` is for the shared mode (provider required, throws
// otherwise), `useExpand` is for the isolated mode (no id needed).

type Ctx = {
  expandedId: string | null;
  setExpanded: React.Dispatch<React.SetStateAction<string | null>>;
};

const ExpandGroupContext = React.createContext<Ctx | null>(null);

export function ExpandGroup({ children }: { children: React.ReactNode }) {
  const [expandedId, setExpanded] = React.useState<string | null>(null);
  return (
    <ExpandGroupContext.Provider value={{ expandedId, setExpanded }}>
      {children}
    </ExpandGroupContext.Provider>
  );
}

// Shared "one expanded at a time" state. Caller picks an id; tapping a
// row already expanded collapses it, tapping any other row swaps. Throws
// if no `<ExpandGroup>` ancestor — that's intentional, the failure mode
// you want is "I called this in the wrong place" not "it silently fell
// back to local state."
export function useExpandGroup(id: string) {
  const ctx = React.useContext(ExpandGroupContext);
  if (ctx === null) {
    throw new Error('useExpandGroup requires an <ExpandGroup> ancestor — use useExpand for isolated state.');
  }
  return {
    expanded: ctx.expandedId === id,
    toggle: () => ctx.setExpanded((prev) => (prev === id ? null : id)),
  };
}

// Local, isolated expand state — independent of any group.
export function useExpand() {
  const [expanded, setExpanded] = React.useState(false);
  return {
    expanded,
    toggle: () => setExpanded((v) => !v),
  };
}
