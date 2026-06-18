/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, expect, it, vi } from 'vitest';
import { load, actions } from '../routes/profile/+page.server';

vi.mock('$env/dynamic/public', () => ({
	env: {
		PUBLIC_BACKEND_URL: 'http://public'
	}
}));

vi.mock('$env/dynamic/private', () => ({
	env: {
		BACKEND_INTERNAL_URL: ''
	}
}));

function mockCookies(session?: string) {
	return {
		get: vi.fn(() => session)
	};
}

describe('profile load', () => {
	it('redirects without session', async () => {
		const cookies = mockCookies();

		await expect(load({ cookies } as any)).rejects.toMatchObject({
			status: 303,
			location: '/auth'
		});
	});

	it('loads profile', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			json: async () => ({
				identity_address: '0x123',
				username: 'alice',
				created_at: null,
				last_login: null
			})
		} as Response);

		const result = await load({
			cookies: mockCookies('token')
		} as any);

		expect(result.profile.username).toBe('alice');
	});

	it('redirects on invalid session', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: false
		} as Response);

		await expect(
			load({
				cookies: mockCookies('bad')
			} as any)
		).rejects.toMatchObject({
			status: 303,
			location: '/auth'
		});
	});
});

describe('profile update', () => {
	it('requires authentication', async () => {
		const form = new FormData();
		form.set('username', 'bob');

		const result = await actions.update({
			cookies: mockCookies(),
			request: {
				formData: async () => form
			}
		} as any);

		expect(result.status).toBe(401);
	});

	it('rejects empty username', async () => {
		const form = new FormData();
		form.set('username', '   ');

		const result = await actions.update({
			cookies: mockCookies('token'),
			request: {
				formData: async () => form
			}
		} as any);

		expect(result.status).toBe(400);
	});

	it('updates username', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue({
			ok: true,
			json: async () => ({
				username: 'newname'
			})
		} as Response);

		const form = new FormData();
		form.set('username', '  newname  ');

		const result = await actions.update({
			cookies: mockCookies('token'),
			request: {
				formData: async () => form
			}
		} as any);

		expect(result).toEqual({
			success: true,
			username: 'newname'
		});
	});
});
