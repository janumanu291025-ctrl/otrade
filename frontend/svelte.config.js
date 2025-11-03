import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),

	kit: {
		adapter: adapter()
	},
	
	onwarn: (warning, handler) => {
		// Suppress A11y warnings about form labels
		if (warning.code === 'a11y-label-has-associated-control') return;
		if (warning.code === 'a11y-no-static-element-interactions') return;
		handler(warning);
	}
};

export default config;
