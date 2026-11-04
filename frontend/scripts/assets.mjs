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

// Notices for every production dependency in the lock file (what can end up in the bundle), with
// the licence text when the package ships one and the SPDX id otherwise.
const lock = JSON.parse(readFileSync(new URL('package-lock.json', root), 'utf8'));
const notices = [];
const names = Object.entries(lock.packages)
  .filter(([key, entry]) => key.startsWith('node_modules/') && !entry.dev && !entry.optional)
  .map(([key]) => key.slice('node_modules/'.length))
  .filter((name, index, all) => all.indexOf(name) === index)
  .sort();
for (const name of names) {
  const base = new URL('node_modules/' + name + '/', root);
  let metadata;
  try {
    metadata = JSON.parse(readFileSync(new URL('package.json', base), 'utf8'));
  } catch {
    continue;
  }
  let license = '';
  for (const file of ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'license', 'License.md', 'LICENCE']) {
    try {
      license = readFileSync(new URL(file, base), 'utf8');
      break;
    } catch {
      /* try the next conventional file name */
    }
  }
  notices.push(
    `${name} ${metadata.version} (${typeof metadata.license === 'string' ? metadata.license : JSON.stringify(metadata.license ?? 'see package')})\n${license}`,
  );
}
writeFileSync(new URL('public/THIRD_PARTY_NOTICES.txt', root), notices.join('\n\n---\n\n'));
