

export const index = 5;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/live-trade/_page.svelte.js')).default;
export const imports = ["_app/immutable/nodes/5.CBsXeWnn.js","_app/immutable/chunks/cb-04oXe.js","_app/immutable/chunks/BeocxfxK.js","_app/immutable/chunks/D6DogDNs.js","_app/immutable/chunks/DCKTeHYU.js","_app/immutable/chunks/CinR6i2W.js"];
export const stylesheets = ["_app/immutable/assets/5.Cb7RfBje.css"];
export const fonts = [];
