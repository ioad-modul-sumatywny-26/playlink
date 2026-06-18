// src/test/signing.test.ts
import { describe, expect, it, vi } from 'vitest';

import {
	buildChatSigningMessage,
	signChatMessage
} from '$lib/signing';


describe('buildChatSigningMessage', () => {
	it('builds the canonical signing payload', () => {
		const result = buildChatSigningMessage(
			'room-123',
			'hello world',
			'2026-01-01T12:00:00Z'
		);

		expect(result).toBe(
			'PlayLink signed chat message\n' +
			'room=room-123\n' +
			'sent_at=2026-01-01T12:00:00Z\n' +
			'content=hello world'
		);
	});


	it('preserves special characters', () => {
		const result = buildChatSigningMessage(
			'abc',
			'hello\nworld',
			'time'
		);

		expect(result).toContain('content=hello\nworld');
	});
});


describe('signChatMessage', () => {
	it('asks the signer to sign the generated message', async () => {
		const signer = {
			signMessage: vi.fn().mockResolvedValue('0xsignature')
		};

		const signature = await signChatMessage(
			signer,
			'room',
			'hello',
			'2026-01-01'
		);

		expect(signature).toBe('0xsignature');

		expect(signer.signMessage).toHaveBeenCalledWith(
			'PlayLink signed chat message\n' +
			'room=room\n' +
			'sent_at=2026-01-01\n' +
			'content=hello'
		);
	});
});