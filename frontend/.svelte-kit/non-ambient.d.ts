
// this file is generated — do not edit it


declare module "svelte/elements" {
	export interface HTMLAttributes<T> {
		'data-sveltekit-keepfocus'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-noscroll'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-preload-code'?:
			| true
			| ''
			| 'eager'
			| 'viewport'
			| 'hover'
			| 'tap'
			| 'off'
			| undefined
			| null;
		'data-sveltekit-preload-data'?: true | '' | 'hover' | 'tap' | 'off' | undefined | null;
		'data-sveltekit-reload'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-replacestate'?: true | '' | 'off' | undefined | null;
	}
}

export {};


declare module "$app/types" {
	export interface AppTypes {
		RouteId(): "/" | "/config" | "/graph" | "/live-trading-v2" | "/live-trading-v2/components" | "/paper-trading" | "/settings";
		RouteParams(): {
			
		};
		LayoutParams(): {
			"/": Record<string, never>;
			"/config": Record<string, never>;
			"/graph": Record<string, never>;
			"/live-trading-v2": Record<string, never>;
			"/live-trading-v2/components": Record<string, never>;
			"/paper-trading": Record<string, never>;
			"/settings": Record<string, never>
		};
		Pathname(): "/" | "/config" | "/config/" | "/graph" | "/graph/" | "/live-trading-v2" | "/live-trading-v2/" | "/live-trading-v2/components" | "/live-trading-v2/components/" | "/paper-trading" | "/paper-trading/" | "/settings" | "/settings/";
		ResolvedPathname(): `${"" | `/${string}`}${ReturnType<AppTypes['Pathname']>}`;
		Asset(): "/favicon.png" | "/favicon.svg" | string & {};
	}
}