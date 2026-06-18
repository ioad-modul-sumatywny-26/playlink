import { browser } from '$app/environment';
import { Wallet } from 'ethers';

/**
 * Session-scoped custody of the message-signing key (issue #59).
 *
 * The auth flow derives a wallet from the recovery phrase but otherwise
 * discards it, keeping only the JWT cookie. To sign every chat message the
 * private key must remain available on the chat route, so we stash it in
 * `sessionStorage`: it survives reloads within the tab and is cleared when the
 * tab closes (or on logout). This is the realistic model for a self-custody
 * web wallet without a browser extension; the key is XSS-exposed, the same
 * exposure class as any in-page secret.
 */
const STORAGE_KEY = 'playlink.sk';

/** Persists the signing key for the current tab session. */
export function saveSigningKey(privateKey: string): void {
	if (!browser) return;
	try {
		sessionStorage.setItem(STORAGE_KEY, privateKey);
	} catch (e) {
		console.error('Could not persist signing key', e);
	}
}

/** Returns a signer for the stored key, or null when none is available. */
export function loadSigner(): Wallet | null {
	if (!browser) return null;
	const privateKey = sessionStorage.getItem(STORAGE_KEY);
	if (!privateKey) return null;
	try {
		return new Wallet(privateKey);
	} catch (e) {
		console.error('Stored signing key is invalid; discarding', e);
		sessionStorage.removeItem(STORAGE_KEY);
		return null;
	}
}

/** Forgets the signing key (called on logout). */
export function clearSigningKey(): void {
	if (!browser) return;
	sessionStorage.removeItem(STORAGE_KEY);
}
