import { env } from '$env/dynamic/public';

/**
 * Returns the effective backend HTTP URL.
 * When the page is loaded locally in a browser (localhost or 127.0.0.1),
 * connects directly to http://<host>:8000 to allow local development and testing
 * without requiring public DNS resolution or external tunnels.
 * Otherwise falls back to env.PUBLIC_BACKEND_URL.
 */
export function getBackendUrl(): string {
	if (typeof window !== 'undefined' && window.location) {
		const host = window.location.hostname;
		if (host === 'localhost' || host === '127.0.0.1') {
			return `http://${host}:8000`;
		}
	}
	return env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
}

/**
 * Returns the effective WebSocket URL.
 * When loaded locally in a browser, connects to ws://<host>:8000.
 */
export function getWsUrl(): string {
	if (typeof window !== 'undefined' && window.location) {
		const host = window.location.hostname;
		if (host === 'localhost' || host === '127.0.0.1') {
			return `ws://${host}:8000`;
		}
	}
	return env.PUBLIC_WS_URL || 'ws://localhost:8000';
}
