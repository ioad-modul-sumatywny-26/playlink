import { afterEach, describe, expect, it, vi } from 'vitest';
import { POST } from '../routes/api/client-errors/+server';

function call(body: unknown, ip = '203.0.113.1') {
	const request = new Request('http://localhost/api/client-errors', {
		method: 'POST',
		headers: { 'content-type': 'application/json', 'cf-connecting-ip': ip },
		body: typeof body === 'string' ? body : JSON.stringify(body)
	});
	return POST({ request, getClientAddress: () => '10.0.0.1' } as never);
}

describe('client error endpoint', () => {
	afterEach(() => vi.restoreAllMocks());

	it('logs a clipped error as one JSON line', async () => {
		const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
		const res = await call(
			{ path: '/rooms', message: 'x'.repeat(1000), stack: 's' },
			'198.51.100.1'
		);
		expect(res.status).toBe(204);
		const entry = JSON.parse(spy.mock.calls[0][0] as string);
		expect(entry).toMatchObject({ level: 'ERROR', event: 'client_error', path: '/rooms' });
		expect(entry.error).toHaveLength(300);
	});

	it('rejects malformed bodies', async () => {
		expect((await call('not json', '198.51.100.2')).status).toBe(400);
	});

	it('rate limits one address', async () => {
		vi.spyOn(console, 'error').mockImplementation(() => {});
		let last = 204;
		for (let i = 0; i < 22; i += 1) last = (await call({ message: 'e' }, '198.51.100.3')).status;
		expect(last).toBe(429);
	});
});
