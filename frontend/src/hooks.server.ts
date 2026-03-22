import { jwtDecode } from 'jwt-decode';

/** @type {import('@sveltejs/kit').Handle} */
export async function handle({ event, resolve }) {
	const session = event.cookies.get('session');

	if (session) {
		try {
			// Decode the JWT to get user info (sub is the identity address)
			const decoded = jwtDecode(session);
			event.locals.user = {
				address: decoded.sub
			};
		} catch (e) {
			// Invalid token
			event.cookies.delete('session', { path: '/' });
		}
	}

	return await resolve(event);
}
