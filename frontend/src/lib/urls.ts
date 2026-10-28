import { env } from '$env/dynamic/public';

/** Normalize a configured URL: trim whitespace and drop a trailing slash. */
function clean(value: string | undefined): string | null {
	const trimmed = value?.trim();
	return trimmed ? trimmed.replace(/\/$/, '') : null;
}

function isLocalHost(): boolean {
	if (typeof window === 'undefined') return false;
	return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
}

/**
 * Effective backend HTTP URL.
 *
 * Production deployments set PUBLIC_BACKEND_URL per region at runtime. The
 * localhost fallback exists only for a plain `bun dev` / single-container dev
 * environment; it must not silently point production traffic at a user's own
 * machine when the variable is missing.
 */
export function getBackendUrl(): string {
	const configured = clean(env.PUBLIC_BACKEND_URL);
	if (configured) return configured;
	if (isLocalHost()) return `http://${window.location.hostname}:8000`;
	console.error('PUBLIC_BACKEND_URL is not configured');
	return '';
}

/** Effective WebSocket base URL. */
export function getWsUrl(): string {
	const configured = clean(env.PUBLIC_WS_URL);
	if (configured) return configured;
	if (isLocalHost()) return `ws://${window.location.hostname}:8000`;
	console.error('PUBLIC_WS_URL is not configured');
	return '';
}
