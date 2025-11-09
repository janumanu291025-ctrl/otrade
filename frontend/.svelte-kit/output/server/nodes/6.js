

export const index = 6;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/paper-trading/_page.svelte.js')).default;
export const imports = ["_app/immutable/nodes/6.CIBvHOd7.js","_app/immutable/chunks/CHJ9xm1E.js","_app/immutable/chunks/DfoOZhRR.js","_app/immutable/chunks/D6YF6ztN.js","_app/immutable/chunks/DehCaVFO.js"];
export const stylesheets = [];
export const fonts = [];
