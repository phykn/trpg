export type ChatRequest = {
  query: string;
  think: boolean;
};

export type ChatChunk = {
  answer: string | null;
};
