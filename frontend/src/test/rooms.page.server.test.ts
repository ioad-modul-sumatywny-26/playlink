/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, expect, it, vi } from 'vitest';
import { actions, load } from '../routes/rooms/+page.server';

vi.mock('$env/dynamic/public', () => ({
	env: {
		PUBLIC_BACKEND_URL: 'http://localhost:8000'
	}
}));

vi.mock('$env/dynamic/private', () => ({
	env: {}
}));

vi.mock('jwt-decode', () => ({
	jwtDecode: () => ({
		sub: '0x123',
		username: 'bob',
		is_admin: false
	})
}));

const cookies = (token = 'token') => ({
	get: vi.fn(() => token)
});

describe('rooms load', () => {
	it('loads without login', async () => {
		const result = await load({
			cookies: cookies(undefined)
		} as any);

		expect(result.isAuthenticated).toBe(true);
	});

	it('loads logged in user', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: false
		} as Response);

		const result = await load({
			cookies: cookies()
		} as any);

		expect(result.user.address).toBe('0x123');
	});
});

describe('create action', () => {
	it('rejects unauthenticated users', async () => {
		const result = await actions.create({
			cookies: cookies(undefined),
			request: {
				formData: async () => new FormData()
			}
		} as any);

		expect(result.status).toBe(400);
	});

	it('rejects missing fields', async () => {
		const result = await actions.create({
			cookies: cookies(),
			request: {
				formData: async () => new FormData()
			}
		} as any);

		expect(result.status).toBe(400);
	});
});

describe('game actions', () => {
	it('rejects empty game', async () => {
		const form = new FormData();
		form.set('name', '');

		const result = await actions.addGame({
			cookies: cookies(),
			request: {
				formData: async () => form
			}
		} as any);

		expect(result.status).toBe(400);
	});
});
