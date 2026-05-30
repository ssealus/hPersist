// icons.jsx — Compact icon set drawn inline, monoline 1.5 stroke
// Keep these geometric and technical to match the console aesthetic.

const I = (d, props = {}) => (
  <svg width={props.size || 14} height={props.size || 14} viewBox="0 0 16 16"
       fill="none" stroke="currentColor" strokeWidth="1.4"
       strokeLinecap="round" strokeLinejoin="round" {...props}>
    {d}
  </svg>
);

const Icon = {
  Dash:   (p) => I(<><rect x="2" y="2" width="5" height="5" rx=".5"/><rect x="9" y="2" width="5" height="5" rx=".5"/><rect x="2" y="9" width="5" height="5" rx=".5"/><rect x="9" y="9" width="5" height="5" rx=".5"/></>, p),
  Plus:   (p) => I(<><path d="M8 3v10M3 8h10"/></>, p),
  Server: (p) => I(<><rect x="2" y="3" width="12" height="4" rx=".5"/><rect x="2" y="9" width="12" height="4" rx=".5"/><circle cx="4.5" cy="5" r=".5" fill="currentColor"/><circle cx="4.5" cy="11" r=".5" fill="currentColor"/></>, p),
  Stack:  (p) => I(<><path d="M2 5l6-3 6 3-6 3-6-3z"/><path d="M2 9l6 3 6-3"/><path d="M2 12l6 3 6-3"/></>, p),
  Cog:    (p) => I(<><circle cx="8" cy="8" r="2"/><path d="M8 1.5v1.6M8 12.9v1.6M14.5 8h-1.6M3.1 8H1.5M12.6 3.4l-1.1 1.1M4.5 11.5L3.4 12.6M12.6 12.6l-1.1-1.1M4.5 4.5L3.4 3.4"/></>, p),
  Bolt:   (p) => I(<><path d="M9 1L3 9h4l-1 6 6-8H8z"/></>, p),
  Search: (p) => I(<><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></>, p),
  Net:    (p) => I(<><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c1.8 2 2.8 4.5 2.8 6S9.8 12 8 14c-1.8-2-2.8-4.5-2.8-6S6.2 4 8 2z"/></>, p),
  Wrench: (p) => I(<><path d="M11.5 3a3 3 0 00-3.7 3.7L2 12.5l1.5 1.5 5.8-5.8A3 3 0 1011.5 3z"/></>, p),
  Chart:  (p) => I(<><path d="M2 13V3M2 13h12M5 10v-3M8 10V5M11 10V7"/></>, p),
  Pulse:  (p) => I(<><path d="M2 8h2l2-5 3 10 2-5h3"/></>, p),
  Down:   (p) => I(<><path d="M4 6l4 4 4-4"/></>, p),
  Up:     (p) => I(<><path d="M4 10l4-4 4 4"/></>, p),
  Right:  (p) => I(<><path d="M6 4l4 4-4 4"/></>, p),
  Left:   (p) => I(<><path d="M10 4l-4 4 4 4"/></>, p),
  Check:  (p) => I(<><path d="M3 8l3 3 7-7"/></>, p),
  X:      (p) => I(<><path d="M4 4l8 8M12 4l-8 8"/></>, p),
  Dot:    (p) => I(<><circle cx="8" cy="8" r="2" fill="currentColor"/></>, p),
  Doc:    (p) => I(<><path d="M3 2h7l3 3v9H3z"/><path d="M10 2v3h3"/></>, p),
  Upload: (p) => I(<><path d="M8 11V2M5 5l3-3 3 3M2 13h12"/></>, p),
  Download:(p) => I(<><path d="M8 2v9M5 8l3 3 3-3M2 13h12"/></>, p),
  CSV:    (p) => I(<><path d="M3 2h7l3 3v9H3z"/><path d="M10 2v3h3M5 9h2M5 11h4M5 13h3"/></>, p),
  Archive:(p) => I(<><rect x="2" y="3" width="12" height="3" rx=".5"/><path d="M3 6v7h10V6M6 8h4"/></>, p),
  Eye:    (p) => I(<><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z"/><circle cx="8" cy="8" r="2"/></>, p),
  Trash:  (p) => I(<><path d="M3 4h10M5 4V2h6v2M5 4l1 10h4l1-10"/></>, p),
  Edit:   (p) => I(<><path d="M2 14l1-3 8-8 2 2-8 8-3 1z"/></>, p),
  Refresh:(p) => I(<><path d="M14 8a6 6 0 11-2-4.5M14 1v4h-4"/></>, p),
  Play:   (p) => I(<><path d="M5 3l8 5-8 5z" fill="currentColor"/></>, p),
  Pause:  (p) => I(<><rect x="4" y="3" width="3" height="10" fill="currentColor"/><rect x="9" y="3" width="3" height="10" fill="currentColor"/></>, p),
  Stop:   (p) => I(<><rect x="3" y="3" width="10" height="10" fill="currentColor"/></>, p),
  Folder: (p) => I(<><path d="M2 5V3h4l1 2h7v8H2z"/></>, p),
  Filter: (p) => I(<><path d="M2 3h12l-5 6v5l-2-1V9z"/></>, p),
  Sort:   (p) => I(<><path d="M5 2v12M2 11l3 3 3-3M11 14V2M14 5l-3-3-3 3"/></>, p),
  Sun:    (p) => I(<><circle cx="8" cy="8" r="3"/><path d="M8 1v1M8 14v1M1 8h1M14 8h1M3 3l.8.8M12.2 12.2l.8.8M3 13l.8-.8M12.2 3.8l.8-.8"/></>, p),
  Moon:   (p) => I(<><path d="M13 9.5A6 6 0 116.5 3 4.5 4.5 0 0013 9.5z"/></>, p),
  Logs:   (p) => I(<><path d="M3 3h10M3 6h10M3 9h7M3 12h10"/></>, p),
  Lock:   (p) => I(<><rect x="3" y="7" width="10" height="7" rx="1"/><path d="M5 7V5a3 3 0 016 0v2"/></>, p),
  Key:    (p) => I(<><circle cx="6" cy="9" r="3"/><path d="M8 7.5L14 1.5M11 3.5l1.5 1.5"/></>, p),
  Layers: (p) => I(<><path d="M8 2L2 5l6 3 6-3-6-3zM2 11l6 3 6-3M2 8l6 3 6-3"/></>, p),
  Cube:   (p) => I(<><path d="M8 2L2 5v6l6 3 6-3V5zM2 5l6 3 6-3M8 8v6"/></>, p),
  Cpu:    (p) => I(<><rect x="4" y="4" width="8" height="8" rx="1"/><rect x="6" y="6" width="4" height="4" rx=".5"/><path d="M6 2v2M10 2v2M6 12v2M10 12v2M2 6h2M2 10h2M12 6h2M12 10h2"/></>, p),
  Mem:    (p) => I(<><rect x="2" y="5" width="12" height="6" rx="1"/><path d="M5 5v6M8 5v6M11 5v6M4 13v1M8 13v1M12 13v1"/></>, p),
  Disk:   (p) => I(<><circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2"/></>, p),
  Power:  (p) => I(<><path d="M5 3.5A5 5 0 108 14a5 5 0 003-9.5M8 1v6"/></>, p),
  Ext:    (p) => I(<><path d="M6 3H3v10h10v-3M9 2h5v5M14 2l-6 6"/></>, p),
  Copy:   (p) => I(<><rect x="5" y="5" width="9" height="9" rx="1"/><path d="M2 11V2h9"/></>, p),
  Info:   (p) => I(<><circle cx="8" cy="8" r="6"/><path d="M8 5v.01M8 8v3"/></>, p),
  Alert:  (p) => I(<><path d="M8 2l7 12H1z"/><path d="M8 6v4M8 12v.01"/></>, p),
  Diff:   (p) => I(<><path d="M6 3v8m0 0l-2-2m2 2l2-2M10 13V5m0 0L8 7m2-2l2 2"/></>, p),
  Globe:  (p) => I(<><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 2 3 4 3 6s-1 4-3 6c-2-2-3-4-3-6s1-4 3-6z"/></>, p),
  Term:   (p) => I(<><rect x="2" y="3" width="12" height="10" rx="1"/><path d="M5 7l2 2-2 2M9 11h3"/></>, p),
};
Icon.ArrowRight = Icon.Right;
Icon.ArrowLeft  = Icon.Left;

window.Icon = Icon;
