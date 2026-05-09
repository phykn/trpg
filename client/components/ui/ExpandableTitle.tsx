import { Expandable } from './Expandable';

const TITLE_LINE_HEIGHT = 21;
const TITLE_CLASS = 'font-serif-medium text-title text-fg-default';

export function ExpandableTitle({ text, color }: { text: string; color?: string }) {
  return (
    <Expandable
      contentKey={text}
      lineHeight={TITLE_LINE_HEIGHT}
      pressableClassName="flex-1 min-w-0"
      textClassName={TITLE_CLASS}
      textStyle={color ? { color } : undefined}
      measureText={text}
    >
      {text}
    </Expandable>
  );
}
