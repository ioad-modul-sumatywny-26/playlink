import { describe, expect, it, vi } from 'vitest';

// adjust this import path
import {
	isChatMessage,
	isRoomMember,
	isRsvpStatus,
	isRsvpEntry,
	isRoomEventState,
	parseFrame
} from '$lib/chatStore';

vi.mock('$env/dynamic/public', () => ({
	env: {
		PUBLIC_WS_URL: 'ws://localhost:3000',
		PUBLIC_BACKEND_URL: 'http://localhost:3000'
	}
}));

describe('chat validation', () => {
	it('accepts valid chat messages', () => {
		const message = {
			id: 1,
			sender_address: '0x123',
			sender_username: 'alice',
			content: 'hello',
			created_at: new Date().toISOString()
		};

		expect(isChatMessage(message)).toBe(true);
	});

	it('rejects invalid chat messages', () => {
		expect(
			isChatMessage({
				id: 'wrong',
				content: 'hello'
			})
		).toBe(false);
	});

	it('accepts valid room members', () => {
		expect(
			isRoomMember({
				address: '0xabc',
				username: 'bob',
				is_admin: true
			})
		).toBe(true);
	});

	it('rejects invalid room members', () => {
		expect(
			isRoomMember({
				address: '0xabc',
				username: 'bob',
				is_admin: 'yes'
			})
		).toBe(false);
	});

	it('validates RSVP status', () => {
		expect(isRsvpStatus('present')).toBe(true);
		expect(isRsvpStatus('absent')).toBe(true);
		expect(isRsvpStatus('maybe')).toBe(true);
		expect(isRsvpStatus('nope')).toBe(false);
	});

	it('accepts valid RSVP entries', () => {
		expect(
			isRsvpEntry({
				address: '0xabc',
				username: 'alice',
				status: 'present',
				updated_at: new Date().toISOString()
			})
		).toBe(true);
	});

	it('accepts valid event state', () => {
		expect(
			isRoomEventState({
				starts_at: '2026-01-01',
				ends_at: '2026-01-02',
				created_by: '0xabc',
				created_at: '2026-01-01',
				updated_at: '2026-01-01',
				rsvps: [
					{
						address: '0xabc',
						username: 'alice',
						status: 'maybe',
						updated_at: '2026-01-01'
					}
				]
			})
		).toBe(true);
	});
});

describe('parseFrame', () => {
	it('parses a message frame', () => {
		const frame = JSON.stringify({
			type: 'message',
			message: {
				id: 1,
				sender_address: '0xabc',
				sender_username: 'alice',
				content: 'hello',
				created_at: '2026-01-01'
			}
		});

		const result = parseFrame(frame);

		expect(result).toEqual({
			type: 'message',
			message: expect.objectContaining({
				content: 'hello'
			})
		});
	});

	it('returns null for bad JSON', () => {
		expect(parseFrame('not json')).toBe(null);
	});

	it('returns null for unknown frames', () => {
		expect(
			parseFrame(
				JSON.stringify({
					type: 'banana'
				})
			)
		).toBe(null);
	});
});
