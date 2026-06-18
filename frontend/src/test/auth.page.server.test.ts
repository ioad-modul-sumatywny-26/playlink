/* eslint-disable @typescript-eslint/no-explicit-any */

import { describe, expect, it, vi } from 'vitest';

import { load, actions } from '../routes/auth/+page.server';


vi.mock('jwt-decode', () => ({
	jwtDecode: vi.fn()
}));

import { jwtDecode } from 'jwt-decode';


function mockCookies() {
	return {
		get: vi.fn(),
		set: vi.fn(),
		delete: vi.fn()
	};
}


describe('auth page server load', () => {
	it('returns no user when no session exists', async () => {
		const cookies = mockCookies();

		cookies.get.mockReturnValue(undefined);

		const result = await load({
			cookies
		} as any);

		expect(result).toEqual({
			user: null
		});
	});


	it('returns user from valid token', async () => {
		const cookies = mockCookies();

		cookies.get.mockReturnValue('token');

		vi.mocked(jwtDecode).mockReturnValue({
			sub: '0x123',
			username: 'alice'
		});

		const result = await load({
			cookies
		} as any);

		expect(result).toEqual({
			user: {
				address: '0x123',
				username: 'alice'
			}
		});
	});


	it('clears invalid token', async () => {
		const cookies = mockCookies();

		cookies.get.mockReturnValue('bad-token');

		vi.mocked(jwtDecode).mockReturnValue({});

		const result = await load({
			cookies
		} as any);

		expect(cookies.delete)
			.toHaveBeenCalledWith('session', { path: '/' });

		expect(result).toEqual({
			user: null
		});
	});
});


describe('login action', () => {

	it('rejects missing token', async () => {
		const cookies = mockCookies();

		const request = {
			formData: async () => new FormData()
		};

		const result = await actions.login({
			request,
			cookies
		} as any);

		expect(result).toEqual({
			success: false,
			error: 'No token provided'
		});
	});


	it('stores token', async () => {
		const cookies = mockCookies();

		const form = new FormData();
		form.set('token', 'abc123');

		const request = {
			formData: async () => form
		};

		const result = await actions.login({
			request,
			cookies
		} as any);


		expect(cookies.set)
			.toHaveBeenCalled();

		expect(result)
			.toEqual({
				success: true
			});
	});
});


describe('logout action', () => {
	it('deletes session cookie', async () => {
		const cookies = mockCookies();

		const result = await actions.logout({
			cookies
		} as any);

		expect(cookies.delete)
			.toHaveBeenCalledWith('session', { path: '/' });

		expect(result)
			.toEqual({
				success: true
			});
	});
});