

export const index = 7;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/live-trade/orders/_page.svelte.js')).default;
export const imports = ["_app/immutable/nodes/7.DNYuh9KY.js","_app/immutable/chunks/cb-04oXe.js","_app/immutable/chunks/D6DogDNs.js","_app/immutable/chunks/BeocxfxK.js","_app/immutable/chunks/C7KyscHc.js"];
export const stylesheets = ["_app/immutable/assets/7.CUdGwISx.css"];
export const fonts = [];
