import { cpSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath, URL } from 'node:url';
const root = new URL('../', import.meta.url);
mkdirSync(new URL('public', root), { recursive: true });
for (const name of ['fonts', 'brand', 'phones'])
  cpSync(
    fileURLToPath(new URL('../../symport/web_assets/' + name, import.meta.url)),
    fileURLToPath(new URL('public/' + name, root)),
    { recursive: true },
  );

const notices = [];
for (const name of [
  'react',
  'react-dom',
  'scheduler',
  '@tanstack/react-query',
  '@tanstack/query-core',
  'zod',
  'wavesurfer.js',
]) {
  const base = new URL('node_modules/' + name + '/', root);
  const metadata = JSON.parse(readFileSync(new URL('package.json', base), 'utf8'));
  const license = readFileSync(new URL('LICENSE', base), 'utf8');
  notices.push(name + ' ' + metadata.version + '\n' + license);
}
writeFileSync(new URL('public/THIRD_PARTY_NOTICES.txt', root), notices.join('\n\n---\n\n'));
