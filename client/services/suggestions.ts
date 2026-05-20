import { ko } from '@/locale/ko';

export type GraphSuggestion = {
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
  const rawLabel = value.label.trim();
  const inputText = value.input_text.trim();
  if (!rawLabel || !inputText) return null;
  const intent = value.intent ?? null;
  return { label: displayLabel(rawLabel, intent), inputText, intent };
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
    label: displayLabel(label, typeof item.intent === 'string' ? item.intent : null),
    inputText,
    intent: typeof item.intent === 'string' ? item.intent : null,
  };
}

function displayLabel(label: string, intent: string | null): string {
  const normalized = label.trim().toLowerCase();
  if (intent === 'inspect' && normalized === 'inspect') return ko.suggestionIntent.inspect;
  if (intent === 'move' && normalized === 'move') return ko.suggestionIntent.move;
  if (intent === 'talk' && normalized === 'talk') return ko.suggestionIntent.talk;
  if (intent === 'use' && normalized === 'use') return ko.suggestionIntent.use;
  if (intent === 'combat' && normalized === 'combat') return ko.suggestionIntent.combat;
  if (intent === 'quest' && normalized === 'quest') return ko.suggestionIntent.quest;
  return label;
}
