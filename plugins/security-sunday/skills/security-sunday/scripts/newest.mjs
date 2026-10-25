// Newest version of each package in its own major (minor for 0.x), and the newest one older
// than 48 hours (the release age). Reads the npm registry, installs nothing.
// usage: node newest.mjs next@15.5.27 react@19.3.0 ...
const now = Date.now();
const cut = 48 * 3600e3;
const key = (v) => v.split('.').map(Number);
for (const arg of process.argv.slice(2)) {
  const at = arg.lastIndexOf('@');
  const name = arg.slice(0, at), cur = arg.slice(at + 1);
  const r = await fetch(`https://registry.npmjs.org/${name.replace('/', '%2F')}`);
  if (!r.ok) { console.log(`${name}: registry ${r.status}`); continue; }
  const j = await r.json();
  const [M, m] = key(cur);
  const same = Object.keys(j.versions)
    .filter((v) => /^\d+\.\d+\.\d+$/.test(v))
    .filter((v) => { const [a, b] = key(v); return M === 0 ? a === 0 && b === m : a === M; })
    .sort((x, y) => { const p = key(x), q = key(y); return p[0] - q[0] || p[1] - q[1] || p[2] - q[2]; });
  const newest = same.at(-1);
  const old = [...same].reverse().find((v) => now - Date.parse(j.time[v]) > cut);
  const age = (v) => ((now - Date.parse(j.time[v])) / 3600e3).toFixed(0) + 'h';
  console.log(`${name.padEnd(32)} ${cur.padEnd(10)} newest ${newest} (${age(newest)})  take ${old}  latest-tag ${j['dist-tags'].latest}`);
}
