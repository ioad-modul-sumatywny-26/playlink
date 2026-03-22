import { jwtDecode } from 'jwt-decode';

/** @type {import('@sveltejs/kit').Handle} */
export async function handle({ event, resolve }) {
	const session = event.cookies.get('session');

	if (session) {
		try {
			// Decode the JWT to get user info (sub is the identity address)
			const decoded = jwtDecode(session);

			// Check if token is expired (exp is in seconds)
			if (decoded.exp && decoded.exp * 1000 < Date.now()) {
				throw new Error('Token expired');
			}

			event.locals.user = {
				address: decoded.sub
			};
		} catch (e) {
			// Invalid or expired token
			event.cookies.delete('session', { path: '/' });
		}
	}

	return await resolve(event);
}
