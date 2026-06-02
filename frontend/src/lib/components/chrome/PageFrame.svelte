<script lang="ts">
	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();
</script>

<div class="page-frame anim-frame-in">
	<!-- Stone-wall backdrop: warm dark brown + subtle quatrefoil pattern + soft torch glow.
	     Replaces the previous black void: panels sit ON the wall, not float in space. -->
	<div class="frame-back" aria-hidden="true">
		<div class="wall-pattern"></div>
		<div class="vignette"></div>
	</div>

	<!-- The carved iron frame: 4 corner ornaments + 4 hairline edges -->
	<div class="frame-chrome" aria-hidden="true">
		<svg class="corner corner-tl" viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg">
			<defs>
				<linearGradient id="goldA" x1="0" y1="0" x2="1" y2="1">
					<stop offset="0%" stop-color="#e3bc74" stop-opacity="0.85" />
					<stop offset="60%" stop-color="#8a6c3a" stop-opacity="0.7" />
					<stop offset="100%" stop-color="#3d3930" stop-opacity="0.4" />
				</linearGradient>
			</defs>
			<g fill="none" stroke="url(#goldA)" stroke-width="1.2">
				<path d="M0 1 H72" />
				<path d="M1 0 V72" />
				<path d="M0 6 H64" stroke-opacity="0.55" />
				<path d="M6 0 V64" stroke-opacity="0.55" />
				<!-- inner knot -->
				<path d="M14 14 L36 14 L36 22 L22 22 L22 36 L14 36 Z" stroke-opacity="0.7" />
				<path d="M22 22 L30 30 M14 36 L36 14" stroke-opacity="0.45" />
				<circle cx="22" cy="22" r="2.2" fill="#c29d59" stroke="none" />
				<!-- diagonal stem -->
				<path d="M44 6 L62 6 M6 44 L6 62" stroke-opacity="0.5" />
				<path d="M50 14 L62 14 L62 26" stroke-opacity="0.4" />
				<path d="M14 50 L14 62 L26 62" stroke-opacity="0.4" />
			</g>
		</svg>
		<svg
			class="corner corner-tr"
			viewBox="0 0 96 96"
			xmlns="http://www.w3.org/2000/svg"
			style="transform: scaleX(-1)"
		>
			<g fill="none" stroke="url(#goldA)" stroke-width="1.2">
				<path d="M0 1 H72" />
				<path d="M1 0 V72" />
				<path d="M0 6 H64" stroke-opacity="0.55" />
				<path d="M6 0 V64" stroke-opacity="0.55" />
				<path d="M14 14 L36 14 L36 22 L22 22 L22 36 L14 36 Z" stroke-opacity="0.7" />
				<path d="M22 22 L30 30 M14 36 L36 14" stroke-opacity="0.45" />
				<circle cx="22" cy="22" r="2.2" fill="#c29d59" stroke="none" />
				<path d="M44 6 L62 6 M6 44 L6 62" stroke-opacity="0.5" />
				<path d="M50 14 L62 14 L62 26" stroke-opacity="0.4" />
				<path d="M14 50 L14 62 L26 62" stroke-opacity="0.4" />
			</g>
		</svg>
		<svg
			class="corner corner-bl"
			viewBox="0 0 96 96"
			xmlns="http://www.w3.org/2000/svg"
			style="transform: scaleY(-1)"
		>
			<g fill="none" stroke="url(#goldA)" stroke-width="1.2">
				<path d="M0 1 H72" />
				<path d="M1 0 V72" />
				<path d="M0 6 H64" stroke-opacity="0.55" />
				<path d="M6 0 V64" stroke-opacity="0.55" />
				<path d="M14 14 L36 14 L36 22 L22 22 L22 36 L14 36 Z" stroke-opacity="0.7" />
				<path d="M22 22 L30 30 M14 36 L36 14" stroke-opacity="0.45" />
				<circle cx="22" cy="22" r="2.2" fill="#c29d59" stroke="none" />
				<path d="M44 6 L62 6 M6 44 L6 62" stroke-opacity="0.5" />
				<path d="M50 14 L62 14 L62 26" stroke-opacity="0.4" />
				<path d="M14 50 L14 62 L26 62" stroke-opacity="0.4" />
			</g>
		</svg>
		<svg
			class="corner corner-br"
			viewBox="0 0 96 96"
			xmlns="http://www.w3.org/2000/svg"
			style="transform: scale(-1, -1)"
		>
			<g fill="none" stroke="url(#goldA)" stroke-width="1.2">
				<path d="M0 1 H72" />
				<path d="M1 0 V72" />
				<path d="M0 6 H64" stroke-opacity="0.55" />
				<path d="M6 0 V64" stroke-opacity="0.55" />
				<path d="M14 14 L36 14 L36 22 L22 22 L22 36 L14 36 Z" stroke-opacity="0.7" />
				<path d="M22 22 L30 30 M14 36 L36 14" stroke-opacity="0.45" />
				<circle cx="22" cy="22" r="2.2" fill="#c29d59" stroke="none" />
				<path d="M44 6 L62 6 M6 44 L6 62" stroke-opacity="0.5" />
				<path d="M50 14 L62 14 L62 26" stroke-opacity="0.4" />
				<path d="M14 50 L14 62 L26 62" stroke-opacity="0.4" />
			</g>
		</svg>

		<!-- edge hairlines -->
		<span class="edge edge-top"></span>
		<span class="edge edge-bottom"></span>
		<span class="edge edge-left"></span>
		<span class="edge edge-right"></span>
	</div>

	<div class="frame-inner">
		{@render children?.()}
	</div>
</div>

<style>
	.page-frame {
		position: relative;
		min-height: 100vh;
		padding: clamp(24px, 3vw, 48px);
		background: #0d0d0b;
		overflow: hidden;
	}

	/* Reclaim horizontal space on very small phones. */
	@media (max-width: 380px) {
		.page-frame {
			padding: 14px;
		}
	}

	.frame-back {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}

	.vignette {
		position: absolute;
		inset: 0;
		/* Lighter vignette — only darkens extreme corners, not the panel area. */
		background: radial-gradient(
			ellipse at 50% 45%,
			transparent 50%,
			rgba(0, 0, 0, 0.35) 85%,
			rgba(0, 0, 0, 0.6) 100%
		);
		pointer-events: none;
		z-index: 2;
	}

	/* Quatrefoil / cross repeat pattern, 96px tile, very low contrast.
	   Pattern stroke is now a cool grey to match the slate wall. */
	.wall-pattern {
		position: absolute;
		inset: 0;
		pointer-events: none;
		z-index: 0;
		opacity: 0.45;
		background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'><g fill='none' stroke='%23363430' stroke-width='1' opacity='0.9'><path d='M48 18 C 56 18 60 22 60 30 C 60 38 56 42 48 42 C 40 42 36 38 36 30 C 36 22 40 18 48 18 Z'/><path d='M48 54 C 56 54 60 58 60 66 C 60 74 56 78 48 78 C 40 78 36 74 36 66 C 36 58 40 54 48 54 Z'/><path d='M0 48 L96 48' stroke-opacity='0.18'/><path d='M48 0 L48 96' stroke-opacity='0.18'/><circle cx='0' cy='0' r='2' fill='%23363430' stroke='none'/><circle cx='96' cy='0' r='2' fill='%23363430' stroke='none'/><circle cx='0' cy='96' r='2' fill='%23363430' stroke='none'/><circle cx='96' cy='96' r='2' fill='%23363430' stroke='none'/></g></svg>");
		background-size: 96px 96px;
		mix-blend-mode: screen;
	}

	.frame-chrome {
		position: absolute;
		inset: clamp(16px, 1.6vw, 28px);
		pointer-events: none;
		z-index: 2;
	}

	.corner {
		position: absolute;
		width: clamp(56px, 5vw, 88px);
		height: clamp(56px, 5vw, 88px);
		filter: drop-shadow(0 1px 0 rgba(0, 0, 0, 0.7));
	}
	.corner-tl {
		top: 0;
		left: 0;
	}
	.corner-tr {
		top: 0;
		right: 0;
	}
	.corner-bl {
		bottom: 0;
		left: 0;
	}
	.corner-br {
		bottom: 0;
		right: 0;
	}

	.edge {
		position: absolute;
		background: linear-gradient(
			90deg,
			transparent 0%,
			rgba(194, 157, 89, 0.4) 12%,
			rgba(194, 157, 89, 0.55) 50%,
			rgba(194, 157, 89, 0.4) 88%,
			transparent 100%
		);
	}
	.edge-top {
		top: 0;
		left: 6%;
		right: 6%;
		height: 1px;
	}
	.edge-bottom {
		bottom: 0;
		left: 6%;
		right: 6%;
		height: 1px;
	}
	.edge-left {
		top: 6%;
		bottom: 6%;
		left: 0;
		width: 1px;
		background: linear-gradient(
			180deg,
			transparent 0%,
			rgba(194, 157, 89, 0.4) 12%,
			rgba(194, 157, 89, 0.55) 50%,
			rgba(194, 157, 89, 0.4) 88%,
			transparent 100%
		);
	}
	.edge-right {
		top: 6%;
		bottom: 6%;
		right: 0;
		width: 1px;
		background: linear-gradient(
			180deg,
			transparent 0%,
			rgba(194, 157, 89, 0.4) 12%,
			rgba(194, 157, 89, 0.55) 50%,
			rgba(194, 157, 89, 0.4) 88%,
			transparent 100%
		);
	}

	.frame-inner {
		position: relative;
		z-index: 3;
		max-width: 1400px;
		margin: 0 auto;
		min-height: calc(100vh - clamp(48px, 6vw, 96px));
		display: flex;
		flex-direction: column;
	}

	@media (max-width: 720px) {
		.page-frame {
			padding: 16px;
		}
		.frame-chrome {
			inset: 8px;
		}
	}
</style>
