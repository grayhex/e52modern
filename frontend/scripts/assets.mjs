import { cpSync, mkdirSync } from 'node:fs';
import { fileURLToPath, URL } from 'node:url';
const root = new URL('../', import.meta.url);
mkdirSync(new URL('public', root), { recursive: true });
for (const name of ['fonts', 'brand', 'phones'])
  cpSync(
    fileURLToPath(new URL('../../symport/web_assets/' + name, import.meta.url)),
    fileURLToPath(new URL('public/' + name, root)),
    { recursive: true },
  );
