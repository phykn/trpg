import React from 'react';

// `useExpandGroup` (shared via provider) vs `useExpand` (isolated local) — split so caller intent is explicit.
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

// "One expanded at a time" state shared via provider. Throws without an ancestor — silent fallback would hide misuse.
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
