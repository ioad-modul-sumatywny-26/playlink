import { describe, expect, it, vi } from 'vitest';
import {
	isNullableString,
	isRoomSummary
} from '$lib/roomsStore';

vi.mock('$env/dynamic/public', () => ({
	env: {
		PUBLIC_WS_URL: 'ws://localhost:3000'
	}
}));

vi.mock('$app/environment', () => ({
	browser: false
}));

describe('isNullableString', () => {
	it('accepts strings', () => {
		expect(isNullableString('hello')).toBe(true);
	});

	it('accepts null', () => {
		expect(isNullableString(null)).toBe(true);
	});

	it('rejects other values', () => {
		expect(isNullableString(123)).toBe(false);
		expect(isNullableString({})).toBe(false);
	});
});


describe('isRoomSummary', () => {
	const validRoom = {
		name: 'Lobby 1',
		game: 'Chess',
		lobby_location: 'eu-central',
		players_active: 2,
		players_max: 10,
		member_addresses: ['0xabc'],
		description: 'Test room',
		communicator_link: null,
		requirements: null,
		expires_at: '2026-01-01T00:00:00Z'
	};

	it('accepts valid rooms', () => {
		expect(isRoomSummary(validRoom)).toBe(true);
	});


	it('rejects missing fields', () => {
		const invalid = {
			...validRoom,
			name: undefined
		};

		expect(isRoomSummary(invalid)).toBe(false);
	});


	it('rejects wrong types', () => {
		const invalid = {
			...validRoom,
			players_active: 'two'
		};

		expect(isRoomSummary(invalid)).toBe(false);
	});


	it('allows nullable fields', () => {
		expect(
			isRoomSummary({
				...validRoom,
				description: null,
				communicator_link: null,
				requirements: null
			})
		).toBe(true);
	});


	it('rejects invalid nullable fields', () => {
		expect(
			isRoomSummary({
				...validRoom,
				description: 123
			})
		).toBe(false);
	});
});