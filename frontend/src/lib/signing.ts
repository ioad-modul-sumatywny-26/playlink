/**
 * Per-message cryptographic signing (issue #59).
 *
 * Chat messages are signed with the sender's BIP39-derived key (EIP-191
 * `personal_sign`) so the backend can recover the signer and prove authorship
 * instead of trusting the JWT alone.
 */

/** Anything that can produce an EIP-191 signature — `HDNodeWallet` and
 *  `ethers.Wallet` both satisfy this. */
export interface ChatSigner {
	signMessage(message: string): Promise<string>;
}

/**
 * Canonical text that is signed for a chat message.
 *
 * This MUST stay byte-for-byte identical to the backend builder
 * `_chat_signing_message` in `backend/main.py`, otherwise recovery fails and
 * every message is rejected.
 */
export function buildChatSigningMessage(room: string, content: string, sentAt: string): string {
	return `PlayLink signed chat message\nroom=${room}\nsent_at=${sentAt}\ncontent=${content}`;
}

/** Signs a chat message and returns the EIP-191 signature (0x-hex). */
export async function signChatMessage(
	signer: ChatSigner,
	room: string,
	content: string,
	sentAt: string
): Promise<string> {
	return signer.signMessage(buildChatSigningMessage(room, content, sentAt));
}
