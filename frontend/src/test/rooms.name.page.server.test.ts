/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, expect, it, vi } from 'vitest';
import { load, actions } from '../routes/rooms/[name]/+page.server';

vi.mock('$env/dynamic/public', () => ({
	env: {
		PUBLIC_BACKEND_URL: 'http://localhost:8000'
	}
}));

vi.mock('$env/dynamic/private', () => ({
	env: {
		BACKEND_INTERNAL_URL: ''
	}
}));

vi.mock('jwt-decode', () => ({
	jwtDecode: () => ({
		sub: '0x123',
		username: 'bob',
		is_admin: false
	})
}));

function cookies(token = 'token') {
	return {
		get: vi.fn(() => token)
	};
}

describe('room page load', () => {
	it('redirects when room missing', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: false
		} as Response);

		await expect(
			load({
				cookies: cookies(),
				params: { name: 'missing' }
			} as any)
		).rejects.toMatchObject({
			status: 303,
			location: '/rooms'
		});
	});
});

describe('room actions', () => {
	it('closes a room through the admin backend endpoint', async () => {
		const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true
		} as Response);

		const result = await actions.closeRoom({
			cookies: cookies(),
			params: { name: 'Lobby 2' }
		} as any);

		expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/rooms/Lobby%202', {
			method: 'DELETE',
			headers: { Authorization: 'Bearer token' }
		});
		expect(result).toEqual({ success: true, closed: true });
	});

	it('rejects missing auth', async () => {
		const result = await actions.setRsvp({
			cookies: cookies(undefined),
			params: { name: 'room' },
			request: {
				formData: async () => new FormData()
			}
		} as any);

		expect(result.status).toBe(400);
	});

	it('rejects invalid RSVP', async () => {
		const form = new FormData();
		form.set('status', 'invalid');

		const result = await actions.setRsvp({
			cookies: cookies(),
			params: { name: 'room' },
			request: {
				formData: async () => form
			}
		} as any);

		expect(result.status).toBe(400);
	});

	it('rejects missing kick member', async () => {
		const result = await actions.kickMember({
			cookies: cookies(),
			params: { name: 'room' },
			request: {
				formData: async () => new FormData()
			}
		} as any);

		expect(result.status).toBe(400);
	});
});
