import { jwtDecode } from 'jwt-decode';
import type { Actions, PageServerLoad } from './$types';

interface SessionTokenClaims {
	sub?: string;
	username?: string;
	exp?: number;
}

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('session');

	if (!session) {
		return { user: null, jwt: null };
	}

	try {
		const decoded = jwtDecode<SessionTokenClaims>(session);

		return {
			user: {
				address: decoded.sub ?? '',
				username: decoded.username ?? ''
			},
			jwt: session
		};
	} catch {
		return { user: null, jwt: null };
	}
};

export const actions: Actions = {
	login: async ({ request, cookies }) => {
		const data = await request.formData();
		const token = data.get('token');

		if (typeof token !== 'string' || token.trim() === '') {
			return { success: false, error: 'No token provided' };
		}

		cookies.set('session', token, {
			path: '/',
			httpOnly: true,
			sameSite: 'strict',
			secure: process.env.NODE_ENV === 'production',
			maxAge: 60 * 60
		});

		return { success: true };
	},
	logout: async ({ cookies }) => {
		cookies.delete('session', { path: '/' });
		return { success: true };
	}
};
