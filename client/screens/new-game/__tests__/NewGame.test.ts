import * as fs from 'fs';
import * as path from 'path';

describe('NewGame layout', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'NewGame.tsx'), 'utf8');

  test('places the start action after the character setup fields', () => {
    expect(source.indexOf('<Section label={ko.form.name}>')).toBeLessThan(
      source.indexOf('accessibilityLabel={ko.action.start}'),
    );
    expect(source.indexOf('<Section label={ko.form.race}>')).toBeLessThan(
      source.indexOf('accessibilityLabel={ko.action.start}'),
    );
  });

  test('does not expose an English option before the client has English UI labels', () => {
    expect(source).not.toContain("useState<'ko' | 'en'>");
    expect(source).not.toContain("setLocale('en')");
  });

  test('uses the shared surface atom for the setup panel', () => {
    expect(source).toContain('<Surface variant="floating"');
    expect(source).not.toContain('border border-border-strong bg-canvas-default px-4 py-4 gap-5');
  });
});
