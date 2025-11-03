

export const index = 10;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/live-trade/signals/_page.svelte.js')).default;
export const imports = ["_app/immutable/nodes/10.D_TNsbnK.js","_app/immutable/chunks/cb-04oXe.js","_app/immutable/chunks/D6DogDNs.js","_app/immutable/chunks/BeocxfxK.js","_app/immutable/chunks/DCKTeHYU.js","_app/immutable/chunks/CinR6i2W.js"];
export const stylesheets = [];
export const fonts = [];
