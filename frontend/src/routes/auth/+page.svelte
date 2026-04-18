<script lang="ts">
	import { generateMnemonic, authenticate } from '$lib/auth';
	import MnemonicInput from '$lib/components/MnemonicInput.svelte';
	import { deserialize } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let mnemonic = $state('');
	let loading = $state(false);
	let error = $state('');

	function handleGenerate() {
		mnemonic = generateMnemonic();
		error = '';
	}

	function handleCopy() {
		if (mnemonic) {
			navigator.clipboard.writeText(mnemonic);
		}
	}

	async function startAuth() {
		loading = true;
		error = '';
		try {
			const result = await authenticate(mnemonic);

			const formData = new FormData();
			formData.append('token', result.token);

			const response = await fetch('?/login', {
				method: 'POST',
				body: formData
			});

			const actionResult = deserialize(await response.text());
			if (actionResult.type === 'success') {
				await invalidateAll();
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Authentication failed';
		} finally {
			loading = false;
		}
	}

	async function handleLogout() {
		const response = await fetch('?/logout', { method: 'POST', body: new FormData() });
		const actionResult = deserialize(await response.text());
		if (actionResult.type === 'success') {
			await invalidateAll();
		}
	}
</script>

<div class="auth-page">
	<h1>Identity Management</h1>

	{#if data.user}
		<div class="session-box">
			<h3>Active Session</h3>
			<p><strong>Status:</strong> Authenticated</p>
			<p><strong>Username:</strong> <code>{data.user.username}</code></p>
			<p><strong>Identity Address:</strong> <code>{data.user.address}</code></p>
			<p><strong>JWT:</strong> <code class="jwt">{data.jwt}</code></p>

			<button class="logout-btn" onclick={handleLogout}>Log Out / Clear Session</button>
		</div>
	{:else}
		<p>Access your non-custodial profile using your recovery phrase.</p>

		<div class="auth-container">
			<div class="auth-header">
				<h3>Sign In / Register</h3>
				<div>
					<button onclick={handleCopy} disabled={!mnemonic}>Copy Phrase</button>
					<button onclick={handleGenerate} disabled={loading}> Generate New Phrase </button>
				</div>
			</div>

			<MnemonicInput bind:value={mnemonic} />

			<button
				class="auth-btn"
				onclick={startAuth}
				disabled={loading || !mnemonic || mnemonic.split(' ').length !== 12}
			>
				{loading ? 'Authenticating...' : 'Confirm Identity'}
			</button>

			{#if error}
				<p class="error">{error}</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	h1, h3 {
		font-family: 'Exocet', serif;
		color: #f1e9cd;
		text-transform: uppercase;
		font-weight: normal;
	}

	.auth-page {
		max-width: 800px;
		margin: 2rem auto;
		padding: 2.5rem;
		background: #111111;
		border: 1px solid #23201a;
		border-radius: 12px;
		box-shadow: inset 0 0 40px rgba(0,0,0,0.5), 0 10px 40px rgba(0,0,0,0.8);
		color: #8c877a;
	}

	.auth-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 2rem;
	}

	.session-box,
	.auth-container {
		margin-top: 1.5rem;
		padding: 2rem;
		border: 1px solid #28251e;
		background: #0a0a0b;
		border-radius: 8px;
	}

	strong {
		color: #a39c8c;
		font-family: ui-monospace, monospace;
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}

	code {
		display: block;
		word-break: break-all;
		background: #141415;
		color: #e3bc74;
		padding: 0.8rem;
		margin: 0.5rem 0 1.5rem 0;
		border-radius: 4px;
		border: 1px solid #28251e;
		font-family: ui-monospace, monospace;
		font-size: 0.8rem;
	}

	button {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.75rem;
		letter-spacing: 0.15em;
		padding: 0.8rem 1.5rem;
		border-radius: 6px;
		cursor: pointer;
		text-transform: uppercase;
		transition: all 0.2s;
		background: transparent;
		color: #a39c8c;
		border: 1px solid #3d3930;
	}

	button:hover:not(:disabled) {
		border-color: #e3bc74;
		color: #e3bc74;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.auth-btn, .logout-btn {
		background: #e3bc74;
		color: #1a1405;
		border: none;
		box-shadow: 0 0 15px rgba(227, 188, 116, 0.3);
		font-weight: bold;
		margin-top: 1rem;
		width: 100%;
	}

	.auth-btn:hover:not(:disabled), .logout-btn:hover {
		background: #f1cf8f;
		box-shadow: 0 0 25px rgba(227, 188, 116, 0.5);
		border-color: #f1cf8f;
		color: #1a1405;
	}

	.error {
		color: #ff6b6b;
		margin-top: 1rem;
		font-size: 0.9rem;
	}

	.jwt {
		max-height: 100px;
		overflow-y: auto;
	}
</style>
