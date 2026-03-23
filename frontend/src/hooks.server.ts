import { jwtDecode } from 'jwt-decode';
import type { Handle } from '@sveltejs/kit';

interface SessionTokenClaims {
	sub?: string;
	exp?: number;
}

export const handle: Handle = async ({ event, resolve }) => {
	const session = event.cookies.get('session');

	if (session) {
		try {
			const decoded = jwtDecode<SessionTokenClaims>(session);

			if (decoded.exp && decoded.exp * 1000 < Date.now()) {
				throw new Error('Token expired');
			}

			if (decoded.sub) {
				event.locals.user = {
					address: decoded.sub
				};
			}
		} catch {
			event.cookies.delete('session', { path: '/' });
		}
	}

	return await resolve(event);
};
