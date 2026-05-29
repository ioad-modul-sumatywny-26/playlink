<script lang="ts">
	interface Props {
		title?: string;
		padded?: boolean;
		children?: import('svelte').Snippet;
		actions?: import('svelte').Snippet;
	}

	let { title, padded = true, children, actions }: Props = $props();
</script>

<section class="inner-panel anim-panel-in" class:padded>
	<!-- Stone slab interior with baked-in top highlight + subtle CSS noise. -->
	<div class="panel-stone" aria-hidden="true">
		<div class="stone-grain"></div>
		<div class="stone-light"></div>
	</div>

	<!-- 4 bronze rivets riveted into the frame corners. -->
	<span class="rivet rivet--tl" aria-hidden="true"></span>
	<span class="rivet rivet--tr" aria-hidden="true"></span>
	<span class="rivet rivet--bl" aria-hidden="true"></span>
	<span class="rivet rivet--br" aria-hidden="true"></span>

	{#if title || actions}
		<header class="panel-head">
			{#if title}
				<h2 class="panel-title etched-gold small-caps">{title}</h2>
				<span class="panel-rule"></span>
			{/if}
			{#if actions}
				<div class="panel-actions">{@render actions()}</div>
			{/if}
		</header>
	{/if}

	<div class="panel-body">
		{@render children?.()}
	</div>
</section>

<style>
	/* The panel itself is the stone slab. The bronze "frame" is faked entirely
	   with stacked inset+outset box-shadows on this single element, in this
	   order (outer → inner):
	     - outer black hairline (anchors panel against backdrop)
	     - drop shadow (lifts panel off page)
	     - bronze midtone ring (the bulk of the frame, ~14px)
	     - top/left bronze highlight bevel (inset, ~3px)
	     - bottom/right bronze shadow bevel (inset, ~3px)
	     - dark hairline between bronze and stone
	     - gold hairline (the "money" line that sells the metal-on-stone read) */
	.inner-panel {
		position: relative;
		/* The stone tone is supplied by .panel-stone, but we keep a solid
		   fallback color in case the overlay fails to render. */
		background: var(--stone-panel-mid);
		border: 0;
		margin: 8px;
		box-shadow:
			/* outer carve into bg */
			0 0 0 1px var(--bronze-low),
			/* drop shadow */ 0 14px 40px rgba(0, 0, 0, 0.7),
			0 2px 0 rgba(0, 0, 0, 0.6),
			/* pewter ring (thick) */ 0 0 0 14px var(--bronze-mid),
			/* hairline at the outer edge of the pewter */ 0 0 0 16px var(--bronze-low),
			/* top + left highlight bevel on the pewter (cool, not warm) */ inset 0 2px 0
				rgba(180, 175, 160, 0.45),
			inset 2px 0 0 rgba(180, 175, 160, 0.28),
			/* bottom + right shadow bevel */ inset 0 -2px 0 rgba(0, 0, 0, 0.75),
			inset -2px 0 0 rgba(0, 0, 0, 0.6),
			/* gold hairline kissing the stone (sole warm accent on the metal) */ inset 0 0 0 3px
				var(--gold-hairline),
			/* dark separation line */ inset 0 0 0 4px var(--bronze-low),
			/* inner stone-edge darkening to fake distance from light source */ inset 0 0 60px
				rgba(0, 0, 0, 0.45);
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	/* On very small phones the 8px margin plus the bronze ring leaves too little
	   width for content — trim the margin to claw back ~8px each side. */
	@media (max-width: 380px) {
		.inner-panel {
			margin: 4px;
		}
	}

	/* Mid-grey stone fill with multi-octave fractal noise baked into a data URI.
	   This is the "weathered stone" surface at the panel's center. */
	.panel-stone {
		position: absolute;
		inset: 4px;
		pointer-events: none;
		z-index: 0;
		background:
			/* a touch of warm tint variation across the slab */ linear-gradient(
			180deg,
			var(--stone-panel-light) 0%,
			var(--stone-panel-mid) 55%,
			var(--stone-panel-edge) 100%
		);
	}

	/* CSS-only stone grain via inline SVG turbulence — no external assets. */
	.stone-grain {
		position: absolute;
		inset: 0;
		background-image:
			url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='340' height='340'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.78' numOctaves='2' stitchTiles='stitch' seed='4'/><feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.55 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>"),
			url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='480' height='480'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.06' numOctaves='3' stitchTiles='stitch' seed='9'/><feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.4 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
		background-size:
			340px 340px,
			480px 480px;
		background-blend-mode: overlay;
		mix-blend-mode: overlay;
		opacity: 0.6;
	}

	/* Baked light from the upper third — the "lit panel" feel of D2R Options.
	   Neutral white-ish (not warm gold) so the slate stays cool. */
	.stone-light {
		position: absolute;
		inset: 0;
		background:
			radial-gradient(
				ellipse 75% 55% at 50% 28%,
				rgba(225, 225, 215, 0.16) 0%,
				rgba(225, 225, 215, 0.05) 35%,
				transparent 75%
			),
			radial-gradient(ellipse 110% 70% at 50% 100%, rgba(0, 0, 0, 0.4) 0%, transparent 70%);
	}

	.padded {
		padding: 0;
	}
	.padded .panel-body {
		padding: clamp(20px, 2vw, 32px);
	}
	.padded .panel-head {
		padding: clamp(16px, 1.4vw, 24px) clamp(20px, 2vw, 32px) 0;
	}

	.panel-head {
		position: relative;
		z-index: 2;
		display: flex;
		align-items: baseline;
		gap: 1.25rem;
	}

	.panel-title {
		font-size: var(--fs-h2);
		margin: 0;
		font-family: var(--font-display);
		font-weight: 700;
		letter-spacing: var(--track-loose);
		color: var(--gold-base);
		flex-shrink: 0;
	}

	.panel-rule {
		flex: 1;
		height: 1px;
		background: var(--hair-gold);
		align-self: center;
		margin-bottom: 0.25rem;
	}

	.panel-actions {
		flex-shrink: 0;
		display: flex;
		gap: 0.75rem;
	}

	.panel-body {
		position: relative;
		z-index: 2;
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}

	/* Cast bronze rivets at the four corners — sit on top of the frame
	   (so we offset them by `frame width / 2` from the panel edge into the
	   bronze ring). 12px diameter reads well at typical panel sizes. */
	.rivet {
		position: absolute;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		z-index: 4;
		pointer-events: none;
		background: radial-gradient(
			circle at 32% 28%,
			var(--bronze-rivet-hot) 0%,
			var(--bronze-rivet-mid) 55%,
			var(--bronze-rivet-shadow) 100%
		);
		box-shadow:
			inset 0 -1px 1px rgba(0, 0, 0, 0.65),
			inset 0 1px 1px rgba(220, 215, 200, 0.4),
			0 1px 2px rgba(0, 0, 0, 0.85),
			0 0 4px rgba(120, 116, 105, 0.35);
	}
	/* Position rivets on the centerline of the bronze ring (~7px in from edge). */
	.rivet--tl {
		top: -7px;
		left: -7px;
	}
	.rivet--tr {
		top: -7px;
		right: -7px;
	}
	.rivet--bl {
		bottom: -7px;
		left: -7px;
	}
	.rivet--br {
		bottom: -7px;
		right: -7px;
	}
</style>
