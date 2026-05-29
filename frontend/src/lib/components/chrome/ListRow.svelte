<script lang="ts">
	interface Props {
		selected?: boolean;
		header?: boolean;
		disabled?: boolean;
		member?: boolean;
		onclick?: () => void;
		children?: import('svelte').Snippet;
	}

	let {
		selected = false,
		header = false,
		disabled = false,
		member = false,
		onclick,
		children
	}: Props = $props();

	let pulsing = $state(false);

	const interactive = $derived(!header && !disabled && typeof onclick === 'function');

	function handleClick() {
		if (!interactive) return;
		pulsing = true;
		setTimeout(() => (pulsing = false), 180);
		onclick?.();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (!interactive) return;
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			handleClick();
		}
	}
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
	class="row"
	class:is-header={header}
	class:is-selected={selected && !header}
	class:is-disabled={disabled && !header}
	class:is-interactive={interactive}
	class:is-pulsing={pulsing}
	class:is-member={member && !header}
	role={interactive ? 'button' : 'row'}
	tabindex={interactive ? 0 : undefined}
	aria-disabled={disabled || undefined}
	aria-selected={!header ? selected || undefined : undefined}
	onclick={handleClick}
	onkeydown={handleKeydown}
>
	{#if (selected || member) && !header}
		<span class="select-pip" class:select-pip--member={member && !selected} aria-hidden="true"
		></span>
	{/if}
	{@render children?.()}
</div>

<style>
	.row {
		position: relative;
		display: grid;
		grid-template-columns: var(--list-cols, 1fr);
		gap: var(--list-gap, 1.25rem);
		align-items: center;
		font-family: var(--font-display);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: var(--track-loose);
		color: var(--bone);
		font-size: var(--fs-small);
		padding: clamp(0.85rem, 1.4vw, 1.05rem) clamp(0.75rem, 1.3vw, 1.1rem);
		min-height: 44px;
		/* Use individual border declarations so :is-selected can change colors
		   without changing the box model (no layout shift). */
		border-top: 1px solid transparent;
		border-right: 1px solid transparent;
		border-bottom: 1px solid rgba(58, 44, 31, 0.55);
		border-left: 3px solid transparent;
		background: transparent;
		transition:
			background 140ms ease,
			color 140ms ease,
			border-color 140ms ease,
			box-shadow 160ms ease,
			transform 80ms ease,
			opacity 140ms ease;
		font-feature-settings:
			'smcp' 1,
			'c2sc' 1;
		outline: none;
		border-radius: 0;
	}

	/* Let every cell shrink below its content width so long values (e.g. room
	   names) truncate via ellipsis instead of widening the track and forcing
	   the whole row to overflow horizontally. */
	.row > :global(*) {
		min-width: 0;
	}

	/* Vertical etched separators between columns.
	   Exclude .select-pip so the absolute-positioned indicator isn't reset to relative
	   (which would push it into the first grid track and shift every cell). */
	.row > :global(*:not(:last-child):not(.select-pip)) {
		position: relative;
	}
	.row > :global(*:not(:last-child):not(.select-pip))::after {
		content: '';
		position: absolute;
		top: 18%;
		bottom: 18%;
		right: calc(var(--list-gap, 1.25rem) / -2);
		width: 1px;
		background: linear-gradient(
			180deg,
			transparent 0%,
			rgba(194, 157, 89, 0.18) 25%,
			rgba(194, 157, 89, 0.32) 50%,
			rgba(194, 157, 89, 0.18) 75%,
			transparent 100%
		);
		pointer-events: none;
	}

	.row.is-interactive {
		cursor: pointer;
	}

	.row.is-header {
		color: var(--gold-muted);
		font-size: var(--fs-label);
		letter-spacing: var(--track-extra);
		padding: 0.85rem 1rem;
		min-height: 0;
		border-bottom: 1px solid var(--gold-dark);
		box-shadow:
			inset 0 -2px 0 var(--stone-1),
			inset 0 -3px 0 rgba(194, 157, 89, 0.18);
		cursor: default;
		background: linear-gradient(180deg, rgba(36, 26, 16, 0.55) 0%, rgba(16, 12, 8, 0.55) 100%);
	}

	.row.is-disabled {
		opacity: 0.4;
		cursor: not-allowed;
		pointer-events: none;
	}

	/* Member (joined) state: subtle gold accent on the row, gold pip pinned left. */
	.row.is-member {
		color: var(--bone-bright);
		border-left-color: rgba(227, 188, 116, 0.55);
		background: linear-gradient(
			90deg,
			rgba(227, 188, 116, 0.06) 0%,
			rgba(227, 188, 116, 0.02) 40%,
			transparent 100%
		);
	}

	.row.is-interactive:hover,
	.row.is-interactive:focus-visible {
		color: var(--bone-bright);
		border-left-color: var(--gold-base);
		background: linear-gradient(
			90deg,
			rgba(227, 188, 116, 0.12) 0%,
			rgba(227, 188, 116, 0.04) 35%,
			transparent 100%
		);
		box-shadow:
			inset 0 0 36px rgba(227, 188, 116, 0.12),
			inset 0 1px 0 rgba(227, 188, 116, 0.1),
			inset 0 -1px 0 rgba(0, 0, 0, 0.6);
	}

	/* Selected — only color changes, geometry stays identical to default. */
	.row.is-selected {
		color: var(--bone-bright);
		border-top-color: var(--gold-muted);
		border-right-color: var(--gold-muted);
		border-bottom-color: var(--gold-muted);
		border-left-color: var(--gold-lit);
		background: linear-gradient(
			90deg,
			rgba(227, 188, 116, 0.16) 0%,
			rgba(227, 188, 116, 0.06) 50%,
			transparent 100%
		);
		box-shadow:
			inset 0 0 36px rgba(227, 188, 116, 0.18),
			inset 0 1px 0 rgba(255, 232, 144, 0.18),
			inset 0 -1px 0 rgba(0, 0, 0, 0.6),
			0 0 12px rgba(227, 188, 116, 0.1);
	}

	.row.is-interactive:focus-visible {
		outline: 1px solid var(--gold-lit);
		outline-offset: -1px;
	}

	.row.is-pulsing {
		transform: translateY(1px);
		opacity: 0.85;
	}

	/* Selected indicator: tiny gold orb on the left edge. */
	.row > .select-pip {
		position: absolute;
		left: -3px;
		top: 50%;
		width: 6px;
		height: 6px;
		margin-top: -3px;
		border-radius: 50%;
		background: radial-gradient(
			circle at 30% 30%,
			var(--gold-hot) 0%,
			var(--gold-base) 60%,
			var(--gold-dark) 100%
		);
		box-shadow:
			0 0 6px var(--gold-glow),
			0 0 1px rgba(0, 0, 0, 0.85);
	}

	.select-pip--member {
		opacity: 0.7;
	}

	/* Touch targets: bump padding so rows are tappable. */
	@media (hover: none) and (pointer: coarse) {
		.row {
			min-height: 56px;
			padding: clamp(1rem, 2.4vw, 1.4rem) 1rem;
		}
	}
</style>
