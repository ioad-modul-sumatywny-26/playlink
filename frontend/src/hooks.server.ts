import { jwtDecode } from 'jwt-decode';
import type { Handle, HandleServerError } from '@sveltejs/kit';
import { logLine } from '$lib/server/log';

interface SessionTokenClaims {
	sub?: string;
	exp?: number;
	is_admin?: boolean;
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

export const handleError: HandleServerError = ({ error, event, status }) => {
	const err = error instanceof Error ? error : new Error(String(error));
	logLine('ERROR', 'server_error', {
		event: 'server_error',
		path: event.url.pathname,
		status,
		error: err.message,
		stack: err.stack
	});
	return { message: 'Internal Error' };
};
