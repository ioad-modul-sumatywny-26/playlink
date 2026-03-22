import { jwtDecode } from 'jwt-decode';

export const load = async ({ cookies }) => {
	const session = cookies.get('session');
	if (session) {
		try {
			const decoded = jwtDecode(session);
			return {
				user: {
					address: decoded.sub,
					username: decoded.username
				},
				jwt: session
			};
		} catch (e) {
			return { user: null };
		}
	}
	return { user: null };
};

export const actions = {
	login: async ({ request, cookies }) => {
		const data = await request.formData();
		const token = data.get('token');

		if (!token) {
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
