import type { Actions, PageServerLoad } from './$types';
import { env } from '$env/dynamic/public';
import { env as privateEnv } from '$env/dynamic/private';
import { fail, redirect } from '@sveltejs/kit';
import { jwtDecode } from 'jwt-decode';
import type { RoomEventState } from '$lib/chatStore';

function backendBase(): string {
	return privateEnv.BACKEND_INTERNAL_URL || env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
}

interface SessionTokenClaims {
	sub?: string;
	username?: string;
}

interface RoomDetail {
	name: string;
	game: string;
	players_max: number;
	players_active: number;
	member_addresses: string[];
	members: { address: string; username: string }[];
	description: string | null;
	communicator_link: string | null;
	requirements: string | null;
	created_by: string;
	expires_at: string;
	event: RoomEventState | null;
}

export const load: PageServerLoad = async ({ params, cookies }) => {
	const session = cookies.get('session');
	if (!session) throw redirect(303, '/auth');

	let address: string | null = null;
	let username = 'Unknown';
	try {
		const claims = jwtDecode<SessionTokenClaims>(session);
		if (claims?.sub) address = claims.sub;
		if (claims?.username) username = claims.username;
	} catch {
		throw redirect(303, '/auth');
	}
	if (!address) throw redirect(303, '/auth');

	const baseUrl = backendBase();
	let roomDetail: RoomDetail | null = null;
	try {
		const res = await fetch(`${baseUrl}/rooms/${encodeURIComponent(params.name)}`);
		if (res.ok) {
			roomDetail = (await res.json()) as RoomDetail;
		}
	} catch {
		// treat fetch errors as missing room — fall through to redirect
	}

	if (!roomDetail) {
		throw redirect(303, '/rooms');
	}

	const lower = address.toLowerCase();
	const isMember = roomDetail.member_addresses.some((a) => a.toLowerCase() === lower);
	if (!isMember) {
		throw redirect(303, '/rooms');
	}

	return {
		roomName: roomDetail.name,
		roomGame: roomDetail.game,
		description: roomDetail.description,
		communicatorLink: roomDetail.communicator_link,
		requirements: roomDetail.requirements,
		token: session,
		address,
		username,
		memberAddresses: roomDetail.member_addresses,
		members: roomDetail.members,
		event: roomDetail.event,
		isCreator: roomDetail.created_by.toLowerCase() === lower
	};
};

const VALID_RSVP = new Set(['present', 'absent', 'maybe']);

function localInputToIsoUtc(value: string): string | null {
	// `<input type="datetime-local">` produces values like "2026-06-02T18:30",
	// interpreted in the user's local zone. `new Date(value)` honours that and
	// .toISOString() converts to the UTC ISO form the backend expects.
	if (!value) return null;
	const d = new Date(value);
	if (Number.isNaN(d.getTime())) return null;
	return d.toISOString();
}

export const actions: Actions = {
	scheduleEvent: async ({ request, cookies, params }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const data = await request.formData();
		const startsAtRaw = data.get('starts_at');
		const endsAtRaw = data.get('ends_at');
		if (typeof startsAtRaw !== 'string' || typeof endsAtRaw !== 'string') {
			return fail(400, { error: 'Missing start or end time' });
		}
		const startIso = localInputToIsoUtc(startsAtRaw);
		const endIso = localInputToIsoUtc(endsAtRaw);
		if (!startIso || !endIso) {
			return fail(400, { error: 'Invalid start or end time' });
		}

		const baseUrl = backendBase();
		try {
			const res = await fetch(`${baseUrl}/rooms/${encodeURIComponent(params.name)}/event`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${session}`
				},
				body: JSON.stringify({ starts_at: startIso, ends_at: endIso })
			});
			if (!res.ok) {
				const result = await res.json().catch(() => ({}));
				return fail(res.status, { error: result.detail || 'Failed to schedule event' });
			}
			return { success: true, message: 'Event scheduled' };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	},

	cancelEvent: async ({ cookies, params }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const baseUrl = backendBase();
		try {
			const res = await fetch(`${baseUrl}/rooms/${encodeURIComponent(params.name)}/event`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${session}` }
			});
			if (!res.ok) {
				const result = await res.json().catch(() => ({}));
				return fail(res.status, { error: result.detail || 'Failed to cancel event' });
			}
			return { success: true, message: 'Event cancelled' };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	},

	setRsvp: async ({ request, cookies, params }) => {
		const session = cookies.get('session');
		if (!session) return fail(401, { error: 'Not authenticated' });

		const data = await request.formData();
		const status = data.get('status');
		if (typeof status !== 'string' || !VALID_RSVP.has(status)) {
			return fail(400, { error: 'Invalid RSVP status' });
		}

		const baseUrl = backendBase();
		try {
			const res = await fetch(`${baseUrl}/rooms/${encodeURIComponent(params.name)}/event/rsvp`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${session}`
				},
				body: JSON.stringify({ status })
			});
			if (!res.ok) {
				const result = await res.json().catch(() => ({}));
				return fail(res.status, { error: result.detail || 'Failed to set RSVP' });
			}
			return { success: true, message: 'RSVP saved' };
		} catch {
			return fail(500, { error: 'Server error' });
		}
	}
};
