export type ChatRequest = {
  query: string;
};

export type ChatChunk = {
  answer: string | null;
};
