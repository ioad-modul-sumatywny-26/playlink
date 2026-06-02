import type { Actions, PageServerLoad } from './$types';
import { env } from '$env/dynamic/public';
import { env as privateEnv } from '$env/dynamic/private';
import { fail, redirect } from '@sveltejs/kit';

function backendBase(): string {
	return privateEnv.BACKEND_INTERNAL_URL || env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
}

interface Profile {
	identity_address: string;
	username: string;
	created_at: string | null;
	last_login: string | null;
}

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('session');
	if (!session) {
		throw redirect(303, '/auth');
	}

	const res = await fetch(`${backendBase()}/users/me`, {
		headers: { Authorization: `Bearer ${session}` }
	});

	if (!res.ok) {
		// Stale/invalid session — send the user back to authenticate.
		throw redirect(303, '/auth');
	}

	const data = (await res.json()) as Profile;
	return {
		profile: {
			identity_address: data.identity_address,
			username: data.username,
			created_at: data.created_at,
			last_login: data.last_login
		}
	};
};

export const actions: Actions = {
	update: async ({ request, cookies }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const form = await request.formData();
		const username = form.get('username');
		if (typeof username !== 'string' || username.trim().length === 0) {
			return fail(400, { error: 'Username is required.' });
		}

		try {
			const res = await fetch(`${backendBase()}/users/me`, {
				method: 'PATCH',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${session}`
				},
				body: JSON.stringify({ username: username.trim() })
			});

			if (!res.ok) {
				const result = await res.json().catch(() => ({}));
				return fail(res.status, {
					error: result.detail || 'Failed to update username.',
					username: username.trim()
				});
			}

			const updated = await res.json();
			return { success: true, username: updated.username };
		} catch {
			return fail(500, { error: 'Server error', username: username.trim() });
		}
	}
};
