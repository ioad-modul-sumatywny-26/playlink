import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/public';
import { env as privateEnv } from '$env/dynamic/private';
import { redirect } from '@sveltejs/kit';
import { jwtDecode } from 'jwt-decode';

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
	description: string | null;
	communicator_link: string | null;
	requirements: string | null;
	expires_at: string;
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
	let isMember = false;
	let roomGame = '';
	let description: string | null = null;
	let communicatorLink: string | null = null;
	let requirements: string | null = null;
	try {
		const res = await fetch(`${baseUrl}/rooms/${encodeURIComponent(params.name)}`);
		if (res.ok) {
			const data = (await res.json()) as RoomDetail;
			roomGame = data.game;
			description = data.description;
			communicatorLink = data.communicator_link;
			requirements = data.requirements;
			const lower = address.toLowerCase();
			isMember = data.member_addresses.some((a) => a.toLowerCase() === lower);
		}
	} catch {
		// treat fetch errors as non-member; will redirect below
	}

	if (!isMember) throw redirect(303, '/rooms');

	return {
		roomName: params.name,
		roomGame,
		description,
		communicatorLink,
		requirements,
		token: session,
		address,
		username
	};
};
