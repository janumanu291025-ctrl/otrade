

export const index = 5;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/live-trading-v2/_page.svelte.js')).default;
export const imports = ["_app/immutable/nodes/5.DiLFR87q.js","_app/immutable/chunks/CHJ9xm1E.js","_app/immutable/chunks/DfoOZhRR.js","_app/immutable/chunks/D6YF6ztN.js","_app/immutable/chunks/C1FmrZbK.js"];
export const stylesheets = ["_app/immutable/assets/5.CbqwEogE.css"];
export const fonts = [];
