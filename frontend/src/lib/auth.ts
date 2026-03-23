import { ethers, Mnemonic, HDNodeWallet } from 'ethers';
import { env } from '$env/dynamic/public';

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
	const backendUrl = env.PUBLIC_BACKEND_URL;
	if (!backendUrl) {
		throw new Error('Missing PUBLIC_BACKEND_URL');
	}

	const identity = getIdentityFromMnemonic(mnemonicPhrase);
	const publicAddress = identity.address;

	// Phase 1: Request Challenge
	// Note: We'll keep using searchParams as established in the backend previously,
	// or adjust based on your specific backend implementation.
	const url = new URL(`${backendUrl}/auth/request-nonce`);
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
	const verifyRes = await fetch(`${backendUrl}/auth/verify`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({
			address: publicAddress,
			nonce: nonce,
			signature: signature
		})
	});

	if (!verifyRes.ok) {
		const error = await verifyRes.json();
		throw new Error(error.detail || 'Authentication failed');
	}

	const { token, username } = await verifyRes.json();
	return { token, address: publicAddress, username };
}
