export type GraphSuggestion =
  | string
  | {
      label: string;
      input_text: string;
      intent?: string | null;
      action?: Record<string, unknown> | null;
    };

export type SuggestionChip = {
  label: string;
  inputText: string;
  intent?: string | null;
};

export function normalizeGraphSuggestion(value: GraphSuggestion): SuggestionChip | null {
  if (typeof value === 'string') {
    const text = value.trim();
    return text ? { label: text, inputText: text } : null;
  }
  const label = value.label.trim();
  const inputText = value.input_text.trim();
  if (!label || !inputText) return null;
  return { label, inputText, intent: value.intent ?? null };
}

export function normalizeStoredSuggestion(value: unknown): SuggestionChip | null {
  if (typeof value === 'string') {
    const text = value.trim();
    return text ? { label: text, inputText: text } : null;
  }
  if (!value || typeof value !== 'object') return null;
  const item = value as {
    label?: unknown;
    inputText?: unknown;
    input_text?: unknown;
    intent?: unknown;
  };
  if (typeof item.label !== 'string') return null;
  const rawInput = item.inputText ?? item.input_text;
  if (typeof rawInput !== 'string') return null;
  const label = item.label.trim();
  const inputText = rawInput.trim();
  if (!label || !inputText) return null;
  return {
    label,
    inputText,
    intent: typeof item.intent === 'string' ? item.intent : null,
  };
}
