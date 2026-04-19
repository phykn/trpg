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

export function useExpandGroup(id: string) {
  const ctx = React.useContext(ExpandGroupContext);
  const [local, setLocal] = React.useState(false);
  if (ctx) {
    return {
      expanded: ctx.expandedId === id,
      toggle: () => ctx.setExpanded((prev) => (prev === id ? null : id)),
    };
  }
  return {
    expanded: local,
    toggle: () => setLocal((v) => !v),
  };
}
