import type { Actions, PageServerLoad } from './$types';
import { env } from '$env/dynamic/public';
import { fail } from '@sveltejs/kit';
import { jwtDecode } from 'jwt-decode';

interface SessionTokenClaims {
	sub?: string;
	username?: string;
	exp?: number;
}

function isStringArray(value: unknown): value is string[] {
	return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('session');
	let user = null;
	let games: string[] = [];

	if (session) {
		try {
			const decoded = jwtDecode<SessionTokenClaims>(session);
			if (decoded?.sub) {
				user = { address: decoded.sub };
			}
		} catch {
			// fail token parsing silently here
		}
	}

	try {
		const baseUrl = env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
		const response = await fetch(`${baseUrl}/games`);

		if (response.ok) {
			const data: unknown = await response.json();
			if (isStringArray(data)) {
				games = data;
			}
		}
	} catch {
		// If games cannot be loaded, keep an empty list so the page can still render.
	}

	return {
		isAuthenticated: !!session,
		user,
		games
	};
};

export const actions: Actions = {
	create: async ({ request, cookies }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const data = await request.formData();
		const name = data.get('name');
		const game = data.get('game');
		const players_max = data.get('players_max');

		if (!name || !game || !players_max) {
			return fail(400, { error: 'Missing required fields' });
		}

		console.log('creating room', name, game, players_max);

		try {
			const baseUrl = env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
			const res = await fetch(`${baseUrl}/rooms`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${session}`
				},
				body: JSON.stringify({
					name: name.toString(),
					game: game.toString(),
					players_max: parseInt(players_max.toString(), 10)
				})
			});

			if (!res.ok) {
				const result = await res.json();
				return fail(res.status, { error: result.detail || 'Failed to create room' });
			}
			return { success: true, message: `Successfully created room: ${name}` };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	},

	join: async ({ request, cookies }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const data = await request.formData();
		const room_name = data.get('room_name');

		if (!room_name) return fail(400, { error: 'Missing room name' });

		try {
			const baseUrl = env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
			const res = await fetch(`${baseUrl}/rooms/${encodeURIComponent(room_name.toString())}/join`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${session}` }
			});

			if (!res.ok) {
				const result = await res.json();
				return fail(res.status, { error: result.detail || 'Failed to join room' });
			}
			return { success: true, message: `Successfully joined room: ${room_name}` };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	},

	leave: async ({ request, cookies }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const data = await request.formData();
		const room_name = data.get('room_name');

		if (!room_name) return fail(400, { error: 'Missing room name' });

		try {
			const baseUrl = env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
			const res = await fetch(`${baseUrl}/rooms/${encodeURIComponent(room_name.toString())}/leave`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${session}` }
			});

			if (!res.ok) {
				const result = await res.json();
				return fail(res.status, { error: result.detail || 'Failed to leave room' });
			}
			return { success: true, message: `Successfully left room: ${room_name}` };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	}
};
