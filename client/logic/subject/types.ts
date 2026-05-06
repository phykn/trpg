import type { SubjectPayload } from '@/services/wire.gen';

// Only hp/hpMax is exposed for subjects. mp/mpMax is intentionally absent —
// the subject panel focuses on affinity/role/equipment, and NPC mana is not
// information the player should see. SubjectPayload on the server enforces the
// same invariant (no mp field).
export type Subject = SubjectPayload;
