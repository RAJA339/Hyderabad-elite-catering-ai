/**
 * Top-down illustrations of the signature dishes, drawn in SVG.
 *
 * Each one is a vessel (copper handi, ceramic bowl, glass cup) with the food composed inside
 * it: rice grains, birista, mutton, aubergines, bread, nuts, leaves. Anything repeated — grains,
 * seeds, specks — is laid down by a seeded generator so it looks scattered by hand but renders
 * identically on every visit and on the server. Everything is vector, so it is crisp at any
 * size, weighs a few kilobytes, and needs no image host.
 */

type Rng = () => number;
function rng(seed: number): Rng {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
/** Random point inside a circle of radius r, biased to the middle so mounds read as mounds. */
function inDisc(r: Rng, radius: number, bias = 0.85): [number, number] {
  const a = r() * Math.PI * 2;
  const d = Math.pow(r(), bias) * radius;
  return [200 + Math.cos(a) * d, 200 + Math.sin(a) * d];
}
const pick = <T,>(r: Rng, xs: readonly T[]) => xs[Math.floor(r() * xs.length)];

/* ── shared parts ─────────────────────────────────────────────────────── */

function Defs({ id, body, deep, hi }: { id: string; body: string; deep: string; hi: string }) {
  return (
    <defs>
      <radialGradient id={`${id}-well`} cx="42%" cy="36%" r="70%">
        <stop offset="0" stopColor={hi} />
        <stop offset="0.45" stopColor={body} />
        <stop offset="1" stopColor={deep} />
      </radialGradient>
      <linearGradient id={`${id}-copper`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#F6D3A6" />
        <stop offset="0.25" stopColor="#B9642A" />
        <stop offset="0.5" stopColor="#E9A468" />
        <stop offset="0.75" stopColor="#8E4519" />
        <stop offset="1" stopColor="#D68A4C" />
      </linearGradient>
      <linearGradient id={`${id}-ceramic`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#FFFFFF" />
        <stop offset="0.5" stopColor="#EDE6DA" />
        <stop offset="1" stopColor="#CFC4B3" />
      </linearGradient>
      <radialGradient id={`${id}-sheen`} cx="35%" cy="28%" r="45%">
        <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.55" />
        <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
      </radialGradient>
      <filter id={`${id}-grain`} x="0" y="0" width="100%" height="100%">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="n" />
        <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.18 0" />
        <feComposite in2="SourceGraphic" operator="in" />
      </filter>
      <filter id={`${id}-shadow`} x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="14" />
      </filter>
      <filter id={`${id}-soft`} x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="3" />
      </filter>
    </defs>
  );
}

/** Vessel: a drop shadow, a rim, and the well the food sits in. */
function Vessel({ id, rim, r = 176, well = 152 }: { id: string; rim: "copper" | "ceramic"; r?: number; well?: number }) {
  return (
    <g>
      <ellipse cx="206" cy="222" rx={r} ry={r * 0.92} fill="#000" opacity="0.28" filter={`url(#${id}-shadow)`} />
      <circle cx="200" cy="200" r={r} fill={`url(#${id}-${rim})`} />
      {rim === "copper" && <circle cx="200" cy="200" r={r - 6} fill="none" stroke="#5E2B0E" strokeOpacity="0.55" strokeWidth="2" />}
      {rim === "copper" && <circle cx="200" cy="200" r={r - 12} fill="none" stroke="#FFE2B8" strokeOpacity="0.5" strokeWidth="1.5" />}
      {rim === "ceramic" && <circle cx="200" cy="200" r={r - 8} fill="none" stroke="#B8AB97" strokeOpacity="0.5" strokeWidth="1.5" />}
      <circle cx="200" cy="200" r={well} fill={`url(#${id}-well)`} />
      <circle cx="200" cy="200" r={well} fill="#000" opacity="0.35" filter={`url(#${id}-grain)`} />
      <circle cx="200" cy="200" r={well} fill="none" stroke="#000" strokeOpacity="0.28" strokeWidth="6" />
    </g>
  );
}

function Leaf({ x, y, rot, size = 1, dark = false }: { x: number; y: number; rot: number; size?: number; dark?: boolean }) {
  const fill = dark ? "#2F6B2E" : "#4C9142";
  return (
    <g transform={`translate(${x} ${y}) rotate(${rot}) scale(${size})`}>
      <path d="M0 0c14-12 30-10 34 4-12 10-28 8-34-4z" fill={fill} />
      <path d="M2 0c10-2 20-1 30 3" stroke="#1E4B1E" strokeWidth="1" fill="none" opacity="0.7" strokeLinecap="round" />
    </g>
  );
}
function Lime({ x, y, rot }: { x: number; y: number; rot: number }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${rot})`}>
      <path d="M0 0L30 0A30 30 0 0 1 0 30z" fill="#E9E77E" />
      <path d="M0 0L30 0A30 30 0 0 1 0 30z" fill="none" stroke="#B9B84A" strokeWidth="3" />
      <path d="M4 4L24 4M4 4L4 24M4 4L18 18" stroke="#FFFFFF" strokeOpacity="0.6" strokeWidth="1.5" />
    </g>
  );
}
function Birista({ r, n, cx = 200, cy = 200, radius = 130, bias = 0.6 }: { r: Rng; n: number; cx?: number; cy?: number; radius?: number; bias?: number }) {
  return (
    <g>
      {Array.from({ length: n }, (_, i) => {
        const a = r() * Math.PI * 2;
        const d = Math.pow(r(), bias) * radius;
        const x = cx + Math.cos(a) * d, y = cy + Math.sin(a) * d;
        return <path key={i} d={`M${x} ${y}c${2 + r() * 4} ${-2 - r() * 3} ${4 + r() * 4} ${1 + r() * 3} ${1 + r() * 3} ${3 + r() * 3}`} stroke={pick(r, ["#7A3A12", "#8E4A1B", "#5C2A0C"])} strokeWidth={1.6 + r() * 1.2} fill="none" strokeLinecap="round" opacity={0.85} />;
      })}
    </g>
  );
}

/* ── dishes ────────────────────────────────────────────────────────────── */

export function BiryaniArt({ id = "biryani" }: { id?: string }) {
  const r = rng(11);
  const grains = Array.from({ length: 330 }, () => {
    const [x, y] = inDisc(r, 142, 0.7);
    return { x, y, rot: r() * 180, len: 9 + r() * 6, fill: pick(r, ["#FBF3DF", "#FBF3DF", "#F7EBD0", "#F3C86A", "#EFB347", "#F7D999"]) };
  });
  const mutton = [[150, 170, -20], [238, 160, 25], [190, 236, 10], [258, 228, -30]] as const;
  return (
    <svg viewBox="0 0 400 400" className="dish-art" aria-hidden>
      <Defs id={id} body="#D98F2E" deep="#6A3410" hi="#F5CE7F" />
      <Vessel id={id} rim="copper" well={148} />
      {/* the dough seal, cracked open: a pale ring pressed against the rim */}
      <circle cx="200" cy="200" r="160" fill="none" stroke="#E9CFA2" strokeWidth="13" />
      <circle cx="200" cy="200" r="160" fill="none" stroke="#C9A472" strokeOpacity="0.6" strokeWidth="13" strokeDasharray="30 9 52 14 18 7" />
      <circle cx="200" cy="200" r="153" fill="none" stroke="#7A4A1E" strokeOpacity="0.5" strokeWidth="2.5" />
      <circle cx="200" cy="200" r="166" fill="none" stroke="#FFF3DD" strokeOpacity="0.6" strokeWidth="1.5" />
      {/* the mound: darker base, then grains */}
      <circle cx="200" cy="200" r="150" fill="#C9852A" opacity="0.55" />
      {grains.map((g, i) => <ellipse key={i} cx={g.x} cy={g.y} rx={g.len / 2} ry="2.3" fill={g.fill} transform={`rotate(${g.rot} ${g.x} ${g.y})`} />)}
      {/* mutton pieces, each with a lit edge */}
      {mutton.map(([x, y, rot], i) => (
        <g key={i} transform={`rotate(${rot} ${x} ${y})`}>
          <rect x={x - 22} y={y - 15} width="44" height="30" rx="11" fill="#5A2A0F" />
          <rect x={x - 22} y={y - 15} width="44" height="30" rx="11" fill={`url(#${id}-sheen)`} />
          <path d={`M${x - 14} ${y - 8}c8-4 18-4 26 0`} stroke="#8F5330" strokeWidth="2" fill="none" strokeLinecap="round" />
        </g>
      ))}
      <Birista r={r} n={38} radius={135} />
      {/* saffron threads */}
      {[[130, 120, 20], [250, 110, -30], [110, 230, 60], [270, 270, 15]].map(([x, y, rot], i) => (
        <path key={i} d="M0 0c10-8 20-4 30 2" transform={`translate(${x} ${y}) rotate(${rot})`} stroke="#C4451A" strokeWidth="2" fill="none" strokeLinecap="round" />
      ))}
      <Leaf x={224} y={296} rot={-150} size={1.1} />
      <Leaf x={128} y={280} rot={-20} dark />
      <Leaf x={176} y={110} rot={200} size={0.8} />
      <Lime x={272} y={122} rot={-25} />
      {/* handi highlight */}
      <path d="M62 150a150 150 0 0 1 84-94" stroke="#FFF0D8" strokeOpacity="0.55" strokeWidth="5" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export function HaleemArt({ id = "haleem" }: { id?: string }) {
  const r = rng(23);
  return (
    <svg viewBox="0 0 400 400" className="dish-art" aria-hidden>
      <Defs id={id} body="#B4611C" deep="#4A2408" hi="#E39A48" />
      <Vessel id={id} rim="ceramic" />
      {/* the surface is glossy: ghee pool and a soft swirl */}
      <ellipse cx="172" cy="168" rx="58" ry="34" fill="#F2B95C" opacity="0.7" filter={`url(#${id}-soft)`} />
      <path d="M120 230c30-36 90-40 140-10" stroke="#F8D28A" strokeOpacity="0.55" strokeWidth="6" fill="none" strokeLinecap="round" filter={`url(#${id}-soft)`} />
      <circle cx="200" cy="200" r="152" fill={`url(#${id}-sheen)`} />
      {/* birista in a crescent, the way it is served */}
      <Birista r={r} n={70} cx={250} cy={220} radius={80} bias={0.5} />
      {/* ginger julienne */}
      {[[132, 246, 20], [146, 262, 35], [122, 266, 10]].map(([x, y, rot], i) => <path key={i} d="M0 0l30 -6" transform={`translate(${x} ${y}) rotate(${rot})`} stroke="#F3D48E" strokeWidth="3" strokeLinecap="round" />)}
      {/* coriander */}
      <Leaf x={150} y={130} rot={-40} size={0.55} dark />
      <Leaf x={166} y={118} rot={30} size={0.5} />
      <Leaf x={140} y={150} rot={-80} size={0.45} />
      {/* lime at the rim, mint on top */}
      <Lime x={228} y={112} rot={-160} />
      <Leaf x={278} y={286} rot={-140} size={0.9} />
      {/* a green chili, split */}
      <path d="M96 200c20-16 44-20 70-10" stroke="#3E8A2B" strokeWidth="7" fill="none" strokeLinecap="round" />
      <path d="M96 200c20-16 44-20 70-10" stroke="#8FD17A" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.7" />
    </svg>
  );
}

export function BainganArt({ id = "baingan" }: { id?: string }) {
  const r = rng(37);
  const seeds = Array.from({ length: 46 }, () => { const [x, y] = inDisc(r, 140, 0.55); return { x, y, rot: r() * 180 }; });
  const eggplants = [[150, 172, -35], [246, 150, 20], [196, 250, 75], [268, 244, -60]] as const;
  return (
    <svg viewBox="0 0 400 400" className="dish-art" aria-hidden>
      <Defs id={id} body="#B7481F" deep="#5A1E0E" hi="#DF7A3A" />
      <Vessel id={id} rim="ceramic" />
      {/* oily gravy sheen with peanut-sesame flecks */}
      <ellipse cx="180" cy="160" rx="70" ry="40" fill="#E48A45" opacity="0.5" filter={`url(#${id}-soft)`} />
      {seeds.map((s, i) => <ellipse key={i} cx={s.x} cy={s.y} rx="3.2" ry="1.7" fill={i % 4 === 0 ? "#E8C79A" : "#F8EEDC"} transform={`rotate(${s.rot} ${s.x} ${s.y})`} />)}
      {eggplants.map(([x, y, rot], i) => (
        <g key={i} transform={`translate(${x} ${y}) rotate(${rot})`}>
          <ellipse cx="0" cy="0" rx="40" ry="24" fill="#3A1236" />
          <ellipse cx="-6" cy="-6" rx="20" ry="8" fill="#6E2F63" opacity="0.7" />
          <ellipse cx="-30" cy="-14" rx="10" ry="4" fill="#9B5A8E" opacity="0.5" />
          {/* calyx + stem */}
          <path d="M34 -6l14-4-10 8 14 2-14 4 8 8-14-4-2 12-6-12-10 4z" fill="#3E7A35" />
          <path d="M44 0l18 -4" stroke="#2C5A2A" strokeWidth="4" strokeLinecap="round" />
        </g>
      ))}
      {/* curry leaves + a couple of peanuts */}
      <Leaf x={110} y={250} rot={-30} size={0.7} dark />
      <Leaf x={120} y={262} rot={-55} size={0.6} dark />
      <ellipse cx="150" cy="290" rx="9" ry="6" fill="#C79A5C" /><ellipse cx="168" cy="292" rx="9" ry="6" fill="#B8894F" />
    </svg>
  );
}

export function MeethaArt({ id = "meetha" }: { id?: string }) {
  const r = rng(53);
  const pista = Array.from({ length: 26 }, () => { const [x, y] = inDisc(r, 120, 0.55); return { x, y, rot: r() * 180 }; });
  const bread = [[176, 176, -14], [228, 190, 12], [196, 232, -4], [244, 236, 30], [160, 226, 40]] as const;
  return (
    <svg viewBox="0 0 400 400" className="dish-art" aria-hidden>
      <Defs id={id} body="#E2B565" deep="#9A5A1C" hi="#FBEBC5" />
      <Vessel id={id} rim="ceramic" r={176} well={156} />
      {/* saffron milk pooled around the bread */}
      <ellipse cx="200" cy="210" rx="132" ry="118" fill="#F7D48B" opacity="0.8" />
      <ellipse cx="180" cy="176" rx="70" ry="36" fill="#FFF3D0" opacity="0.7" filter={`url(#${id}-soft)`} />
      {bread.map(([x, y, rot], i) => (
        <g key={i} transform={`translate(${x} ${y}) rotate(${rot})`}>
          <rect x="-34" y="-24" width="68" height="48" rx="10" fill="#C9862F" />
          <rect x="-34" y="-24" width="68" height="48" rx="10" fill={`url(#${id}-sheen)`} />
          <rect x="-30" y="-20" width="60" height="40" rx="8" fill="none" stroke="#F5D08C" strokeOpacity="0.7" strokeWidth="2" />
          <path d="M-20 -8c10-6 26-6 40 0" stroke="#F1C46A" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.9" />
        </g>
      ))}
      {/* silver leaf (varq) — a crumpled highlight on one piece */}
      <path d="M204 156l38 8-6 18-30-6-4-10z" fill="#FFFFFF" opacity="0.72" />
      <path d="M208 160l30 6M206 168l26 4" stroke="#D9D9D9" strokeWidth="1" opacity="0.7" />
      {pista.map((p, i) => <ellipse key={i} cx={p.x} cy={p.y} rx="6" ry="2.6" fill={i % 3 === 0 ? "#6A9A4A" : "#88B15C"} transform={`rotate(${p.rot} ${p.x} ${p.y})`} />)}
      {/* slivered almonds, saffron threads, a rose petal */}
      {[[130, 150, 10], [268, 158, -35], [136, 270, 50]].map(([x, y, rot], i) => <ellipse key={i} cx={x} cy={y} rx="9" ry="3.2" fill="#F7EBD3" stroke="#D9B98C" strokeWidth="1" transform={`rotate(${rot} ${x} ${y})`} />)}
      {[[150, 120, 15], [250, 280, -20], [116, 216, 70]].map(([x, y, rot], i) => <path key={i} d="M0 0c10-8 20-4 30 2" transform={`translate(${x} ${y}) rotate(${rot})`} stroke="#C4451A" strokeWidth="2" fill="none" strokeLinecap="round" />)}
      <path d="M262 122c14-14 30-2 20 12-8 6-18 2-20-12z" fill="#D4536E" opacity="0.9" />
      <path d="M266 126c6-4 12-4 16-1" stroke="#A73A52" strokeWidth="1" fill="none" opacity="0.6" />
    </svg>
  );
}

export function ChaiArt({ id = "chai" }: { id?: string }) {
  const r = rng(71);
  return (
    <svg viewBox="0 0 400 400" className="dish-art" aria-hidden>
      <Defs id={id} body="#B9865A" deep="#5A3018" hi="#E4C39E" />
      {/* saucer */}
      <ellipse cx="180" cy="228" rx="150" ry="140" fill="#000" opacity="0.28" filter={`url(#${id}-shadow)`} />
      <circle cx="176" cy="206" r="150" fill={`url(#${id}-ceramic)`} />
      <circle cx="176" cy="206" r="136" fill="none" stroke="#B8AB97" strokeOpacity="0.55" strokeWidth="1.5" />
      <circle cx="176" cy="206" r="118" fill="#E8DFD0" />
      {/* cup: rim, tea, froth */}
      <circle cx="176" cy="206" r="98" fill="#FFFFFF" />
      <circle cx="176" cy="206" r="98" fill="none" stroke="#CFC4B3" strokeWidth="2" />
      <circle cx="176" cy="206" r="86" fill={`url(#${id}-well)`} />
      <circle cx="176" cy="206" r="86" fill="#000" opacity="0.3" filter={`url(#${id}-grain)`} />
      <circle cx="176" cy="206" r="86" fill="none" stroke="#000" strokeOpacity="0.2" strokeWidth="5" />
      {/* the malai froth: a soft ring and a swirl */}
      <circle cx="176" cy="206" r="72" fill="none" stroke="#EAD2B0" strokeOpacity="0.85" strokeWidth="14" filter={`url(#${id}-soft)`} />
      <path d="M132 214c14-30 56-40 92-14" stroke="#F3E2C8" strokeWidth="5" fill="none" strokeLinecap="round" opacity="0.9" />
      <path d="M150 190c10-6 26-8 40-2" stroke="#FFF7EA" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.8" />
      {/* cup handle */}
      <path d="M270 190c26-4 34 30 6 40" stroke="#FFFFFF" strokeWidth="14" fill="none" strokeLinecap="round" />
      <path d="M270 190c26-4 34 30 6 40" stroke="#CFC4B3" strokeWidth="2" fill="none" strokeLinecap="round" />
      {/* Osmania biscuit at the edge, crumbs */}
      <g transform="translate(306 296)">
        <ellipse cx="4" cy="8" rx="46" ry="42" fill="#000" opacity="0.25" filter={`url(#${id}-shadow)`} />
        <circle cx="0" cy="0" r="44" fill="#DBA75B" />
        <circle cx="0" cy="0" r="44" fill={`url(#${id}-sheen)`} />
        <circle cx="0" cy="0" r="40" fill="none" stroke="#B98338" strokeWidth="2" opacity="0.8" />
        <circle cx="0" cy="0" r="28" fill="none" stroke="#C48E42" strokeWidth="1.5" opacity="0.8" />
        {Array.from({ length: 9 }, (_, i) => { const a = (i / 9) * Math.PI * 2; return <circle key={i} cx={Math.cos(a) * 16} cy={Math.sin(a) * 16} r="2.2" fill="#A8712C" />; })}
        <circle cx="0" cy="0" r="2.2" fill="#A8712C" />
      </g>
      {Array.from({ length: 8 }, (_, i) => { const a = r() * 6.28; const d = 52 + r() * 30; return <circle key={i} cx={306 + Math.cos(a) * d} cy={296 + Math.sin(a) * d} r={1.4 + r() * 1.4} fill="#C48E42" />; })}
    </svg>
  );
}
