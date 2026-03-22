import { ethers, Mnemonic, HDNodeWallet } from 'ethers';
import { PUBLIC_BACKEND_URL } from '$env/static/public';

/**
 * Derives a cryptographic identity (private/public key pair) from a 12-word mnemonic.
 */
export function getIdentityFromMnemonic(phrase: string): HDNodeWallet {
	try {
		const mnemonic = Mnemonic.fromPhrase(phrase);
		return HDNodeWallet.fromMnemonic(mnemonic);
	} catch (e) {
		console.error('Wallet derivation failed:', e);
		throw new Error('Invalid mnemonic phrase');
	}
}

/**
 * Generates a new 12-word mnemonic.
 */
export function generateMnemonic(): string {
	return Mnemonic.fromEntropy(ethers.randomBytes(16)).phrase;
}

/**
 * Signs a message with a cryptographic identity.
 */
export async function signMessage(identity: HDNodeWallet, message: string): Promise<string> {
	return await identity.signMessage(message);
}

/**
 * Full authentication flow.
 */
export async function authenticate(mnemonicPhrase: string) {
	const identity = getIdentityFromMnemonic(mnemonicPhrase);
	const publicAddress = identity.address;

	// Phase 1: Request Challenge
	// Note: We'll keep using searchParams as established in the backend previously,
	// or adjust based on your specific backend implementation.
	const url = new URL(`${PUBLIC_BACKEND_URL}/auth/request-nonce`);
	url.searchParams.append('address', publicAddress);

	const nonceRes = await fetch(url, { method: 'POST' });

	if (!nonceRes.ok) {
		const error = await nonceRes.json();
		throw new Error(error.detail || 'Failed to request nonce');
	}

	const { nonce } = await nonceRes.json();

	// Phase 2: Local Signing
	const messageText = `Sign in to Playlink\nNonce: ${nonce}`;
	const signature = await signMessage(identity, messageText);

	// Phase 3: Verification
	const verifyUrl = new URL(`${PUBLIC_BACKEND_URL}/auth/verify`);
	verifyUrl.searchParams.append('address', publicAddress);
	verifyUrl.searchParams.append('nonce', nonce);
	verifyUrl.searchParams.append('signature', signature);

	const verifyRes = await fetch(verifyUrl, { method: 'POST' });

	if (!verifyRes.ok) {
		const error = await verifyRes.json();
		throw new Error(error.detail || 'Authentication failed');
	}

	const { token, username } = await verifyRes.json();
	return { token, address: publicAddress, username };
}
