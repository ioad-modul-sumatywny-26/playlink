<script>
	import { generateMnemonic, authenticate } from '$lib/auth';
	import MnemonicInput from '$lib/components/MnemonicInput.svelte';
	import { deserialize } from '$app/forms';
	import { invalidateAll } from '$app/navigation';

	/** @type {{ data: any }} */
	let { data } = $props();

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
			error = e.message;
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
	.auth-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.session-box,
	.auth-container {
		margin-top: 1rem;
		padding: 1rem;
		border: 1px solid #ccc;
	}

	code {
		display: block;
		word-break: break-all;
		background: #eee;
		padding: 0.2rem;
		margin: 0.5rem 0;
	}

	.jwt {
		max-height: 100px;
		overflow-y: auto;
	}
</style>
