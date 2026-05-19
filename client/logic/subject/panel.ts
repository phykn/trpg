import { DASH, characterMeta, withDeath } from '@/components/ui';
import { ko } from '@/locale/ko';
import type { PanelSlot } from '@/logic/info-panel';

import type { Subject } from './types';

export function buildSubjectSlot(subject: Subject | null, opts?: { dot?: boolean }): PanelSlot {
  if (!subject) {
    return {
      id: 'person',
      chip: { short: ko.subject.chip, dot: opts?.dot },
      panel: { empty: true, title: ko.subject.chip },
    };
  }
  return {
    id: 'person',
    chip: { short: ko.subject.chip, dot: opts?.dot },
    panel: {
      title: withDeath(subject.name, subject.alive),
      meta: [{ text: characterMeta(subject.level, subject.raceJob, subject.gender) }],
      sections: [
        { label: ko.panel.role, text: subject.role || DASH },
      ],
    },
  };
}
