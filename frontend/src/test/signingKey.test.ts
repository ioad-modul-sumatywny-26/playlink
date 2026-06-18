import { describe, expect, it, vi, beforeEach } from 'vitest';
import { Wallet } from 'ethers';

vi.mock('$app/environment', () => ({
	browser: true
}));

import {
	saveSigningKey,
	loadSigner,
	clearSigningKey
} from '$lib/signingKey';


const PRIVATE_KEY =
	'0x0123456789012345678901234567890123456789012345678901234567890123';


let wallet: Wallet;

beforeEach(() => {
	sessionStorage.clear();
	wallet = new Wallet(PRIVATE_KEY);
});


describe('signing key storage', () => {
	it('saves a private key', () => {
		saveSigningKey(wallet.privateKey);

		expect(sessionStorage.getItem('playlink.sk'))
			.toBe(wallet.privateKey);
	});


	it('loads a signer from storage', () => {
		saveSigningKey(wallet.privateKey);

		const signer = loadSigner();

		expect(signer).not.toBeNull();
		expect(signer?.address)
			.toBe(wallet.address);
	});


	it('clears the signing key', () => {
		saveSigningKey(wallet.privateKey);

		clearSigningKey();

		expect(sessionStorage.getItem('playlink.sk'))
			.toBe(null);
	});


	it('removes invalid stored keys', () => {
		sessionStorage.setItem(
			'playlink.sk',
			'not-a-private-key'
		);

		expect(loadSigner()).toBe(null);
		expect(sessionStorage.getItem('playlink.sk'))
			.toBe(null);
	});
});