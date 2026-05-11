const fs = require('fs');
const path = require('path');

const CLIENT_ROOT = path.resolve(__dirname, '..', '..');

function read(relativePath: string): string {
  return fs.readFileSync(path.join(CLIENT_ROOT, relativePath), 'utf8');
}

describe('suggestion chip wiring', () => {
  test('passes game suggestions from Playing into Composer', () => {
    const playing = read('screens/play/Playing.tsx');

    expect(playing).toContain('suggestions');
    expect(playing).toContain('suggestions={suggestions}');
  });

  test('Composer renders suggestions as pressable chips', () => {
    const composer = read('components/composer/Composer.tsx');

    expect(composer).toContain('suggestions');
    expect(composer).toContain('suggestions.map');
    expect(composer).toContain('suggestion.label');
    expect(composer).toContain('suggestion.inputText');
  });
});
