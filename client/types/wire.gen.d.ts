// AUTO-GENERATED. Do not edit by hand. Run `npm run gen` from client/.

export type Code = string;
export type Message = string;

export interface Wire {
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "ErrorPayload".
 */
export interface ErrorPayload {
  code: Code;
  message: Message;
  [k: string]: unknown;
}
