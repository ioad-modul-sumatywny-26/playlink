<script lang="ts">
	type Tone = 'gold' | 'blood' | 'green' | 'iron';
	type Position = 'bottom-right' | 'top-center' | 'center';

	interface Props {
		open?: boolean;
		title: string;
		tone?: Tone;
		modal?: boolean;
		inline?: boolean;
		position?: Position;
		width?: string;
		closeable?: boolean;
		onclose?: () => void;
		children?: import('svelte').Snippet;
		footer?: import('svelte').Snippet;
	}

	let {
		open = $bindable(false),
		title,
		tone = 'iron',
		modal = false,
		inline = false,
		position = 'bottom-right',
		width = '420px',
		closeable = true,
		onclose,
		children,
		footer
	}: Props = $props();

	function close() {
		if (!closeable) return;
		open = false;
		onclose?.();
	}

	function onOverlayClick(e: MouseEvent) {
		if (e.target === e.currentTarget) close();
	}

	function onOverlayKey(e: KeyboardEvent) {
		if (e.key === 'Enter' || e.key === ' ') {
			if (e.target === e.currentTarget) {
				e.preventDefault();
				close();
			}
		}
	}

	$effect(() => {
		if (!open || !modal) return;
		const handler = (e: KeyboardEvent) => {
			if (e.key === 'Escape') close();
		};
		window.addEventListener('keydown', handler);
		const prevOverflow = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		return () => {
			window.removeEventListener('keydown', handler);
			document.body.style.overflow = prevOverflow;
		};
	});
</script>

{#if open}
	{#if inline}
		<div
			class="sys-dialog inline tone-{tone}"
			style="--dlg-width: {width};"
			role="status"
			aria-live="polite"
		>
			<span class="left-bar" aria-hidden="true"></span>
			<header class="title-bar">
				<span class="top-rule" aria-hidden="true"></span>
				<h3 class="title">{title}</h3>
				{#if closeable}
					<button class="close-btn" type="button" aria-label="Close" onclick={close}>&times;</button
					>
				{/if}
			</header>
			<div class="body">
				{@render children?.()}
			</div>
			{#if footer}
				<footer class="footer">{@render footer()}</footer>
			{/if}
		</div>
	{:else if modal}
		<div
			class="sys-overlay"
			role="presentation"
			onclick={onOverlayClick}
			onkeydown={onOverlayKey}
			tabindex="-1"
		>
			<div
				class="sys-dialog modal pos-center tone-{tone}"
				style="--dlg-width: {width};"
				role="dialog"
				aria-modal="true"
				aria-label={title}
			>
				<span class="left-bar" aria-hidden="true"></span>
				<header class="title-bar">
					<span class="top-rule" aria-hidden="true"></span>
					<h3 class="title">{title}</h3>
					{#if closeable}
						<button class="close-btn" type="button" aria-label="Close" onclick={close}
							>&times;</button
						>
					{/if}
				</header>
				<div class="body">
					{@render children?.()}
				</div>
				{#if footer}
					<footer class="footer">{@render footer()}</footer>
				{/if}
			</div>
		</div>
	{:else}
		<div
			class="sys-dialog floating pos-{position} tone-{tone}"
			style="--dlg-width: {width};"
			role="status"
			aria-live="polite"
		>
			<span class="left-bar" aria-hidden="true"></span>
			<header class="title-bar">
				<span class="top-rule" aria-hidden="true"></span>
				<h3 class="title">{title}</h3>
				{#if closeable}
					<button class="close-btn" type="button" aria-label="Close" onclick={close}>&times;</button
					>
				{/if}
			</header>
			<div class="body">
				{@render children?.()}
			</div>
			{#if footer}
				<footer class="footer">{@render footer()}</footer>
			{/if}
		</div>
	{/if}
{/if}

<style>
	.sys-overlay {
		position: fixed;
		inset: 0;
		z-index: var(--z-dialog);
		background: rgba(5, 4, 3, 0.78);
		backdrop-filter: blur(2px);
		-webkit-backdrop-filter: blur(2px);
		display: flex;
		align-items: center;
		justify-content: center;
		animation: sys-fade-in 200ms ease-out both;
		border: 0;
		padding: 1rem;
	}

	.sys-dialog {
		position: relative;
		width: var(--dlg-width);
		max-width: calc(100vw - 2rem);
		font-family: var(--font-display);
		color: var(--bone);
		background: linear-gradient(180deg, var(--stone-3) 0%, var(--stone-1) 100%);
		border: 1px solid var(--stone-6);
		border-radius: 0;
		box-shadow: var(--shadow-deep), var(--bevel-out);
	}

	/* Inline variant: no fixed positioning, lives in flow. */
	.sys-dialog.inline {
		width: 100%;
		max-width: 100%;
		animation: sys-fade-in 200ms ease-out both;
	}

	/* Floating variant: fixed in viewport. */
	.sys-dialog.floating {
		position: fixed;
		z-index: var(--z-toast);
	}

	.sys-dialog.floating.pos-bottom-right {
		right: 2rem;
		bottom: 2rem;
		animation: sys-slide-in-right 200ms cubic-bezier(0.16, 1, 0.3, 1) both;
	}

	.sys-dialog.floating.pos-top-center {
		top: 2rem;
		left: 50%;
		transform: translateX(-50%);
		animation: sys-slide-in-top 200ms cubic-bezier(0.16, 1, 0.3, 1) both;
	}

	.sys-dialog.floating.pos-center {
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		animation: sys-scale-in 200ms cubic-bezier(0.16, 1, 0.3, 1) both;
	}

	/* Modal variant: dialog inside overlay flexbox.
	   Capped to the viewport (overlay adds 1rem padding each side → 2rem) and
	   laid out as a column so the body scrolls and the footer stays reachable
	   no matter how tall the content gets. */
	.sys-dialog.modal {
		position: relative;
		animation: sys-scale-in 200ms cubic-bezier(0.16, 1, 0.3, 1) both;
		display: flex;
		flex-direction: column;
		max-height: calc(100dvh - 2rem);
		overflow: hidden;
	}

	.sys-dialog.modal .title-bar,
	.sys-dialog.modal .footer {
		flex-shrink: 0;
	}

	.sys-dialog.modal .body {
		flex: 1 1 auto;
		min-height: 0;
		overflow-y: auto;
	}

	.left-bar {
		position: absolute;
		top: 0;
		bottom: 0;
		left: 0;
		width: 4px;
		background: var(--bone-dim);
		pointer-events: none;
		z-index: 2;
	}

	.tone-gold .left-bar {
		background: var(--gold-muted);
	}
	.tone-blood .left-bar {
		background: var(--blood);
	}
	.tone-green .left-bar {
		background: var(--pip-good);
	}

	.title-bar {
		position: relative;
		height: 36px;
		padding: 0 1.5rem 0 1.25rem;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		border-bottom: 1px solid var(--stone-5);
	}

	.top-rule {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 1px;
		background: var(--bone-dim);
		pointer-events: none;
	}

	.tone-gold .top-rule {
		background: linear-gradient(90deg, transparent 0%, var(--gold-muted) 50%, transparent 100%);
	}
	.tone-blood .top-rule {
		background: linear-gradient(90deg, transparent 0%, var(--blood-bright) 50%, transparent 100%);
	}
	.tone-green .top-rule {
		background: linear-gradient(90deg, transparent 0%, var(--pip-good) 50%, transparent 100%);
	}

	.title {
		flex: 1;
		margin: 0;
		font-family: var(--font-display);
		font-weight: normal;
		font-size: var(--fs-h3);
		text-transform: uppercase;
		letter-spacing: var(--track-loose);
		color: var(--bone-dim);
		text-shadow: 0 1px 0 rgba(0, 0, 0, 0.75);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.tone-gold .title {
		color: var(--gold-base);
		text-shadow:
			0 0 12px rgba(227, 188, 116, 0.22),
			0 1px 0 rgba(0, 0, 0, 0.75);
	}
	.tone-blood .title {
		color: var(--blood-bright);
		text-shadow:
			0 0 12px rgba(181, 54, 54, 0.32),
			0 1px 0 rgba(0, 0, 0, 0.75);
	}
	.tone-green .title {
		color: var(--pip-good);
		text-shadow:
			0 0 10px rgba(127, 191, 92, 0.3),
			0 1px 0 rgba(0, 0, 0, 0.75);
	}

	.close-btn {
		flex-shrink: 0;
		appearance: none;
		background: transparent;
		border: 0;
		color: var(--bone-dim);
		font-family: var(--font-mono);
		font-size: 1.4rem;
		line-height: 1;
		padding: 0 0.25rem;
		cursor: pointer;
		border-radius: 0;
		transition: color 140ms ease;
	}
	.close-btn:hover {
		color: var(--gold-lit);
	}
	.close-btn:focus-visible {
		outline: 1px solid var(--gold-lit);
		outline-offset: 2px;
	}

	.body {
		padding: 1.25rem 1.5rem;
		color: var(--bone);
		font-size: var(--fs-body);
		font-family: var(--font-display);
		line-height: 1.5;
	}

	.footer {
		display: flex;
		flex-direction: row;
		gap: 0.75rem;
		justify-content: flex-end;
		padding: 1rem 1.5rem;
		border-top: 1px solid var(--stone-5);
	}

	@keyframes sys-fade-in {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	@keyframes sys-slide-in-right {
		from {
			opacity: 0;
			transform: translateX(12px);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}

	@keyframes sys-slide-in-top {
		from {
			opacity: 0;
			transform: translate(-50%, -12px);
		}
		to {
			opacity: 1;
			transform: translate(-50%, 0);
		}
	}

	@keyframes sys-scale-in {
		from {
			opacity: 0;
			transform: translate(-50%, -50%) scale(0.96);
		}
		to {
			opacity: 1;
			transform: translate(-50%, -50%) scale(1);
		}
	}

	/* Modal dialog uses no centering transform (flex centers it). */
	.sys-dialog.modal {
		animation-name: sys-modal-scale-in;
	}

	@keyframes sys-modal-scale-in {
		from {
			opacity: 0;
			transform: scale(0.96);
		}
		to {
			opacity: 1;
			transform: scale(1);
		}
	}
</style>
