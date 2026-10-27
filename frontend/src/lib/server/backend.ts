import type { RequestEvent } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';
import { env as privateEnv } from '$env/dynamic/private';

/**
 * Internal base URL used by SvelteKit server loaders and form actions.
 * In compose this is the backend service name; outside Docker it falls back
 * to the public URL so `bun dev` keeps working.
 */
export function backendBase(): string {
	return privateEnv.BACKEND_INTERNAL_URL || env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
}

/**
 * Server-side fetch against the region's backend that forwards the real
 * player IP. The backend trusts CF-Connecting-IP only from the frontend
 * container, so without this header every SSR call would share one
 * rate-limit bucket.
 *
 * Headers are kept as a plain object so existing tests and call sites keep
 * their exact Authorization casing.
 */
export function backendFetch(
	event: Pick<RequestEvent, 'request'>,
	path: string,
	init: RequestInit = {}
): Promise<Response> {
	const headers: Record<string, string> = {};

	if (init.headers) {
		if (init.headers instanceof Headers) {
			init.headers.forEach((value, key) => {
				headers[key] = value;
			});
		} else if (Array.isArray(init.headers)) {
			for (const [key, value] of init.headers) {
				headers[key] = value;
			}
		} else {
			Object.assign(headers, init.headers as Record<string, string>);
		}
	}

	const clientIp = event.request?.headers?.get('cf-connecting-ip');
	if (clientIp) {
		headers['CF-Connecting-IP'] = clientIp;
	}

	return fetch(`${backendBase()}${path}`, { ...init, headers });
}
