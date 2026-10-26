import { jwtDecode } from 'jwt-decode';
import type { Handle } from '@sveltejs/kit';

interface SessionTokenClaims {
	sub?: string;
	exp?: number;
	is_admin?: boolean;
}

const LOCAL_ALLOWED_ORIGINS = new Set([
	'http://localhost:3000',
	'http://127.0.0.1:3000',
	'http://localhost:5173',
	'http://127.0.0.1:5173'
]);

export const handle: Handle = async ({ event, resolve }) => {
	// Custom CSRF check: allow requests matching server origin OR configured ORIGIN OR local development origins
	if (event.request.method !== 'GET' && event.request.method !== 'HEAD') {
		const requestOrigin = event.request.headers.get('origin');
		if (requestOrigin) {
			const configuredOrigin = process.env.ORIGIN?.replace(/\/$/, '');
			const cleanRequestOrigin = requestOrigin.replace(/\/$/, '');
			const isAllowed =
				cleanRequestOrigin === event.url.origin.replace(/\/$/, '') ||
				(configuredOrigin && cleanRequestOrigin === configuredOrigin) ||
				LOCAL_ALLOWED_ORIGINS.has(cleanRequestOrigin);

			if (!isAllowed) {
				return new Response('Cross-site POST form submissions are forbidden', { status: 403 });
			}
		}
	}

	const session = event.cookies.get('session');

	if (session) {
		try {
			const decoded = jwtDecode<SessionTokenClaims>(session);

			if (decoded.exp && decoded.exp * 1000 < Date.now()) {
				throw new Error('Token expired');
			}

			if (decoded.sub) {
				event.locals.user = {
					address: decoded.sub,
					isAdmin: decoded.is_admin === true
				};
			}
		} catch {
			event.cookies.delete('session', { path: '/' });
		}
	}

	return await resolve(event);
};
