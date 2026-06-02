import type { Actions, PageServerLoad } from './$types';
import { env } from '$env/dynamic/public';
import { env as privateEnv } from '$env/dynamic/private';
import { fail } from '@sveltejs/kit';
import { jwtDecode } from 'jwt-decode';
import {
	FALLBACK_LOBBY_LOCATION,
	FALLBACK_LOBBY_LOCATIONS,
	isLobbyLocation,
	type LobbyLocation
} from '$lib/lobbyLocations';

function backendBase(): string {
	return privateEnv.BACKEND_INTERNAL_URL || env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
}

interface SessionTokenClaims {
	sub?: string;
	username?: string;
	exp?: number;
	is_admin?: boolean;
}

function isStringArray(value: unknown): value is string[] {
	return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

interface LobbyLocationsResponse {
	default?: unknown;
	locations?: unknown;
}

function parseLobbyLocations(value: unknown): {
	locations: LobbyLocation[];
	defaultLocation: string;
} {
	const payload = value as LobbyLocationsResponse;
	const locations = Array.isArray(payload?.locations)
		? payload.locations.filter(isLobbyLocation)
		: FALLBACK_LOBBY_LOCATIONS;
	const defaultLocation =
		typeof payload?.default === 'string' && locations.some((l) => l.code === payload.default)
			? payload.default
			: FALLBACK_LOBBY_LOCATION;
	return {
		locations: locations.length > 0 ? locations : FALLBACK_LOBBY_LOCATIONS,
		defaultLocation
	};
}

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('session');
	let user = null;
	let isAdmin = false;
	let games: string[] = [];
	let lobbyLocations = FALLBACK_LOBBY_LOCATIONS;
	let defaultLobbyLocation = FALLBACK_LOBBY_LOCATION;

	if (session) {
		try {
			const decoded = jwtDecode<SessionTokenClaims>(session);
			if (decoded?.sub) {
				user = { address: decoded.sub };
				isAdmin = decoded.is_admin === true;
			}
		} catch {
			// fail token parsing silently here
		}
	}

	try {
		const baseUrl = backendBase();
		const [gamesResponse, locationsResponse] = await Promise.all([
			fetch(`${baseUrl}/games`),
			fetch(`${baseUrl}/lobby-locations`)
		]);

		if (gamesResponse.ok) {
			const data: unknown = await gamesResponse.json();
			if (isStringArray(data)) {
				games = data;
			}
		}

		if (locationsResponse.ok) {
			const data: unknown = await locationsResponse.json();
			const parsed = parseLobbyLocations(data);
			lobbyLocations = parsed.locations;
			defaultLobbyLocation = parsed.defaultLocation;
		}
	} catch {
		// If metadata cannot be loaded, keep fallbacks so the page can still render.
	}

	return {
		isAuthenticated: !!session,
		user,
		isAdmin,
		games,
		lobbyLocations,
		defaultLobbyLocation
	};
};

export const actions: Actions = {
	create: async ({ request, cookies }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const data = await request.formData();
		const name = data.get('name');
		const game = data.get('game');
		const customGame = data.get('custom_game');
		const lobbyLocation = data.get('lobby_location');
		const players_max = data.get('players_max');
		const description = data.get('description');
		const communicator_link = data.get('communicator_link');
		const requirements = data.get('requirements');

		if (!name || !game || !lobbyLocation || !players_max) {
			return fail(400, { error: 'Missing required fields' });
		}

		const selectedGame = game.toString();
		const gameName =
			selectedGame === '__custom__' && typeof customGame === 'string'
				? customGame.trim()
				: selectedGame.trim();
		if (!gameName) {
			return fail(400, { error: 'Game name is required' });
		}

		const optionalText = (value: FormDataEntryValue | null): string | null => {
			if (typeof value !== 'string') return null;
			const trimmed = value.trim();
			return trimmed.length > 0 ? trimmed : null;
		};

		try {
			const baseUrl = backendBase();
			const res = await fetch(`${baseUrl}/rooms`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${session}`
				},
				body: JSON.stringify({
					name: name.toString(),
					game: gameName,
					lobby_location: lobbyLocation.toString(),
					players_max: parseInt(players_max.toString(), 10),
					description: optionalText(description),
					communicator_link: optionalText(communicator_link),
					requirements: optionalText(requirements)
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
			const baseUrl = backendBase();
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
			const baseUrl = backendBase();
			const res = await fetch(
				`${baseUrl}/rooms/${encodeURIComponent(room_name.toString())}/leave`,
				{
					method: 'POST',
					headers: { Authorization: `Bearer ${session}` }
				}
			);

			if (!res.ok) {
				const result = await res.json();
				return fail(res.status, { error: result.detail || 'Failed to leave room' });
			}
			return { success: true, message: `Successfully left room: ${room_name}` };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	},

	deleteRoom: async ({ request, cookies }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const data = await request.formData();
		const room_name = data.get('room_name');
		if (!room_name) return fail(400, { error: 'Missing room name' });

		try {
			const baseUrl = backendBase();
			const res = await fetch(`${baseUrl}/rooms/${encodeURIComponent(room_name.toString())}`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${session}` }
			});

			if (!res.ok) {
				const result = await res.json().catch(() => ({}));
				return fail(res.status, { error: result.detail || 'Failed to close room' });
			}
			return { success: true, message: `Closed room: ${room_name}` };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	},

	addGame: async ({ request, cookies }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const data = await request.formData();
		const name = data.get('name');
		if (typeof name !== 'string' || name.trim() === '') {
			return fail(400, { error: 'Game name is required' });
		}

		try {
			const baseUrl = backendBase();
			const res = await fetch(`${baseUrl}/games`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${session}`
				},
				body: JSON.stringify({ name: name.trim() })
			});

			if (!res.ok) {
				const result = await res.json().catch(() => ({}));
				return fail(res.status, { error: result.detail || 'Failed to add game' });
			}
			return { success: true, message: `Added game: ${name.trim()}` };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	},

	deleteGame: async ({ request, cookies }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const data = await request.formData();
		const name = data.get('name');
		const force = data.get('force') === 'true';
		if (typeof name !== 'string' || name.trim() === '') {
			return fail(400, { error: 'Missing game name' });
		}
		const gameName = name.trim();

		try {
			const baseUrl = backendBase();
			const url = new URL(`${baseUrl}/games/${encodeURIComponent(gameName)}`);
			if (force) url.searchParams.set('force', 'true');
			const res = await fetch(url, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${session}` }
			});

			if (!res.ok) {
				const result = await res.json().catch(() => ({}));
				// 409 means active rooms are still playing this game — surface it as a
				// conflict so the UI can offer a force-delete confirmation.
				if (res.status === 409) {
					return fail(409, {
						error: result.detail || 'Game has active rooms',
						conflict: true,
						game: gameName
					});
				}
				return fail(res.status, { error: result.detail || 'Failed to delete game' });
			}
			return { success: true, message: `Deleted game: ${gameName}` };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	}
};
