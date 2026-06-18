<script lang="ts">
	import { generateMnemonic, authenticate } from '$lib/auth';
	import { clearSigningKey } from '$lib/signingKey';
	import MnemonicInput from '$lib/components/MnemonicInput.svelte';
	import { enhance, deserialize } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import InnerPanel from '$lib/components/chrome/InnerPanel.svelte';
	import SectionTitle from '$lib/components/chrome/SectionTitle.svelte';
	import OrnateButton from '$lib/components/chrome/OrnateButton.svelte';
	import Sigil from '$lib/components/chrome/Sigil.svelte';
	import SystemDialog from '$lib/components/chrome/SystemDialog.svelte';
	import { getHintsState } from '$lib/hintsContext.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let mnemonic = $state('');
	let loading = $state(false);
	let error = $state('');
	let copyStatus = $state<'idle' | 'ok' | 'fail'>('idle');
	let errorOpen = $derived(!!error);

	const hintsState = getHintsState();

	$effect(() => {
		if (data.user) {
			hintsState?.set([{ key: 'L', label: 'Sever Covenant', tone: 'red' }]);
		} else {
			hintsState?.set([
				{ key: 'G', label: 'Generate', tone: 'green' },
				{ key: 'C', label: 'Copy Phrase', tone: 'amber' },
				{ key: 'Enter', label: 'Confirm', tone: 'gold' }
			]);
		}
	});

	function handleGenerate() {
		mnemonic = generateMnemonic();
		error = '';
	}

	async function handleCopy() {
		if (!mnemonic) return;
		try {
			if (navigator.clipboard?.writeText) {
				await navigator.clipboard.writeText(mnemonic);
			} else {
				// HTTP context blocks the async Clipboard API; fall back to the
				// legacy textarea+execCommand path which still works there.
				const ta = document.createElement('textarea');
				ta.value = mnemonic;
				ta.style.position = 'fixed';
				ta.style.opacity = '0';
				document.body.appendChild(ta);
				ta.focus();
				ta.select();
				const ok = document.execCommand('copy');
				document.body.removeChild(ta);
				if (!ok) throw new Error('execCommand failed');
			}
			copyStatus = 'ok';
		} catch {
			copyStatus = 'fail';
		}
		setTimeout(() => (copyStatus = 'idle'), 1500);
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

	let logoutForm: HTMLFormElement | null = $state(null);

	function handleKeydown(e: KeyboardEvent) {
		const target = e.target as HTMLElement | null;
		const tag = target?.tagName?.toLowerCase();
		if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

		if (data.user) {
			if (e.key === 'l' || e.key === 'L') {
				e.preventDefault();
				logoutForm?.requestSubmit();
			}
		} else {
			if (e.key === 'g' || e.key === 'G') {
				e.preventDefault();
				if (!loading) handleGenerate();
			} else if (e.key === 'c' || e.key === 'C') {
				e.preventDefault();
				handleCopy();
			} else if (e.key === 'Enter') {
				if (!loading && mnemonic && mnemonic.split(' ').length === 12) {
					e.preventDefault();
					startAuth();
				}
			}
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<svelte:head>
	<title>PlayLink — Vault Keeper</title>
</svelte:head>

<div class="auth-page anim-content-in">
	{#if data.user}
		<InnerPanel title="Active Covenant">
			<div class="covenant">
				<div class="covenant-head">
					<div class="sigil-halo">
						<Sigil address={data.user.address} size={88} />
					</div>
					<div class="identity">
						<h2 class="username etched-gold">{data.user.username}</h2>
						<div class="address-row">
							<span class="dot good" aria-hidden="true" title="Bonded · session valid"></span>
							<code class="address mono">{data.user.address}</code>
						</div>
					</div>
				</div>

				<div class="action-row">
					<form
						bind:this={logoutForm}
						method="POST"
						action="?/logout"
						class="logout-form"
						use:enhance={() => {
							clearSigningKey();
							return async ({ update }) => {
								await update();
								await invalidateAll();
							};
						}}
					>
						<OrnateButton variant="danger" size="md" type="submit">Sever Covenant</OrnateButton>
					</form>
				</div>
			</div>
		</InnerPanel>
	{:else}
		<InnerPanel title="Vault Keeper">
			<div class="vault">
				<div class="vault-head">
					<p class="prose">
						Access your non-custodial profile using your recovery phrase. Twelve words bind you to
						your covenant — guard them.
					</p>
					<div class="head-actions">
						<OrnateButton variant="secondary" size="sm" onclick={handleGenerate} disabled={loading}>
							Generate New Phrase
						</OrnateButton>
						<OrnateButton variant="ghost" size="sm" onclick={handleCopy} disabled={!mnemonic}>
							{copyStatus === 'ok'
								? 'Copied ✓'
								: copyStatus === 'fail'
									? 'Copy Failed'
									: 'Copy Phrase'}
						</OrnateButton>
					</div>
				</div>

				<span class="hairline-gold"></span>

				<div class="phrase-zone">
					<SectionTitle title="Recovery Phrase" size="small" tone="gold">
						<span class="phrase-counter">
							{mnemonic ? mnemonic.split(' ').filter(Boolean).length : 0} / 12
						</span>
					</SectionTitle>
					<MnemonicInput bind:value={mnemonic} />
				</div>

				{#if error}
					<SystemDialog
						bind:open={errorOpen}
						title="Authentication Failed"
						tone="blood"
						inline
						closeable
						onclose={() => (error = '')}
					>
						<p class="error-body">{error}</p>
					</SystemDialog>
				{/if}

				<span class="hairline-gold"></span>

				<div class="confirm-row">
					<OrnateButton
						variant="primary"
						size="lg"
						fullWidth
						onclick={startAuth}
						disabled={loading || !mnemonic || mnemonic.split(' ').length !== 12}
						{loading}
					>
						{loading ? 'Authenticating…' : 'Confirm Identity'}
					</OrnateButton>
				</div>
			</div>
		</InnerPanel>
	{/if}
</div>

<style>
	.auth-page {
		max-width: 760px;
		margin: 2rem auto;
		padding: 0 1rem;
	}

	.etched-gold {
		font-family: var(--font-display);
		font-weight: normal;
		color: var(--bone-bright);
		text-shadow:
			0 0 14px rgba(227, 188, 116, 0.16),
			0 1px 0 rgba(0, 0, 0, 0.85);
	}

	.mono {
		font-family: var(--font-mono);
	}

	.hairline-gold {
		display: block;
		height: 1px;
		width: 100%;
		background: var(--hair-gold);
		border: 0;
		margin: 1.25rem 0;
	}

	/* ---------- Active covenant ---------- */
	.covenant {
		display: flex;
		flex-direction: column;
	}

	.covenant-head {
		display: flex;
		gap: 1.4rem;
		align-items: center;
	}

	.sigil-halo {
		flex-shrink: 0;
	}

	.identity {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		min-width: 0;
		flex: 1;
	}

	.username {
		margin: 0;
		font-size: 1.9rem;
		letter-spacing: var(--track-display);
		text-transform: uppercase;
		color: var(--bone-bright);
		line-height: 1.05;
		word-break: break-word;
	}

	.address-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		min-width: 0;
	}

	.address {
		display: inline-block;
		font-size: 0.78rem;
		color: var(--bone-muted);
		letter-spacing: 0.04em;
		word-break: break-all;
		white-space: normal;
	}

	.dot {
		display: inline-block;
		width: 8px;
		height: 8px;
		background: var(--bone-dim);
		box-shadow: 0 0 6px rgba(0, 0, 0, 0.6);
		flex-shrink: 0;
	}
	.dot.good {
		background: var(--pip-good);
		box-shadow: 0 0 8px rgba(127, 191, 92, 0.55);
	}

	.action-row {
		display: flex;
		gap: 0.9rem;
		margin-top: 1.6rem;
		flex-wrap: wrap;
	}

	.action-row :global(.ornate) {
		flex: 1;
	}

	.logout-form {
		flex: 1;
		display: flex;
	}

	.logout-form :global(.ornate) {
		flex: 1;
		width: 100%;
	}

	/* ---------- Vault keeper (login) ---------- */
	.vault {
		display: flex;
		flex-direction: column;
	}

	.vault-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1.5rem;
		flex-wrap: wrap;
	}

	.prose {
		margin: 0;
		flex: 1;
		min-width: 220px;
		max-width: 360px;
		font-family: var(--font-display);
		color: var(--bone-muted);
		font-size: 0.95rem;
		line-height: 1.55;
		letter-spacing: 0.02em;
	}

	.head-actions {
		display: flex;
		gap: 0.6rem;
		flex-shrink: 0;
		flex-wrap: wrap;
	}

	.phrase-zone {
		display: flex;
		flex-direction: column;
	}

	.phrase-counter {
		color: var(--gold-muted);
	}

	.error-body {
		margin: 0;
		font-family: var(--font-mono);
		font-size: 0.85rem;
		color: var(--blood-bright);
		line-height: 1.45;
		word-break: break-word;
	}

	.confirm-row {
		display: flex;
	}

	.confirm-row :global(.ornate) {
		width: 100%;
	}

	@media (max-width: 540px) {
		.covenant-head {
			flex-direction: column;
			align-items: flex-start;
		}
		.action-row {
			flex-direction: column;
		}
		.vault-head {
			flex-direction: column;
		}
	}
</style>
