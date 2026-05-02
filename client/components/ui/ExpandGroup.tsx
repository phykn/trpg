import React from 'react';

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

// Throws without an ancestor — silent fallback would hide misuse.
export function useExpandGroup(id: string) {
  const ctx = React.useContext(ExpandGroupContext);
  if (ctx === null) {
    throw new Error('useExpandGroup requires an <ExpandGroup> ancestor.');
  }
  return {
    expanded: ctx.expandedId === id,
    toggle: () => ctx.setExpanded((prev) => (prev === id ? null : id)),
  };
}
