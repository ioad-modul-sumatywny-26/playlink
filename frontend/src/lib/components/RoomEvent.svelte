<script lang="ts">
	import { enhance } from '$app/forms';
	import type { RoomEventState, RsvpEntry, RsvpStatus } from '$lib/chatStore';
	import SectionTitle from '$lib/components/chrome/SectionTitle.svelte';
	import OrnateButton from '$lib/components/chrome/OrnateButton.svelte';
	import D2DatePicker from '$lib/components/chrome/D2DatePicker.svelte';
	import D2TimePicker from '$lib/components/chrome/D2TimePicker.svelte';

	interface Props {
		event: RoomEventState | null;
		isCreator: boolean;
		isMember: boolean;
		viewerAddress: string;
		members: { address: string; username?: string }[];
		formError?: string | null;
	}

	let { event, isCreator, isMember, viewerAddress, members, formError = null }: Props = $props();

	let editing = $state(false);
	let draftStartDate = $state<Date | null>(null);
	let draftEndDate = $state<Date | null>(null);
	let draftStartTime = $state('18:00');
	let draftEndTime = $state('20:00');
	let localError = $state<string | null>(null);

	const viewerLower = $derived(viewerAddress.toLowerCase());

	const myRsvp: RsvpEntry | undefined = $derived(
		event?.rsvps.find((r) => r.address.toLowerCase() === viewerLower)
	);

	function timeToMinutes(t: string): number {
		const m = /^(\d{1,2}):(\d{2})$/.exec(t);
		if (!m) return 0;
		return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
	}

	function formatTimeFromDate(d: Date): string {
		const pad = (n: number) => n.toString().padStart(2, '0');
		return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
	}

	function stripTime(d: Date): Date {
		return new Date(d.getFullYear(), d.getMonth(), d.getDate());
	}

	function addDays(d: Date, days: number): Date {
		return new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);
	}

	function daysBetween(a: Date, b: Date): number {
		const ms = stripTime(b).getTime() - stripTime(a).getTime();
		return Math.round(ms / 86_400_000);
	}

	function combine(date: Date, time: string): Date | null {
		const [h, m] = time.split(':').map((n) => parseInt(n, 10));
		if (Number.isNaN(h) || Number.isNaN(m)) return null;
		return new Date(date.getFullYear(), date.getMonth(), date.getDate(), h, m, 0, 0);
	}

	const todayStart = $derived(stripTime(new Date()));

	const endMinDate = $derived(draftStartDate ?? todayStart);

	const startDateTime = $derived.by(() =>
		draftStartDate ? combine(draftStartDate, draftStartTime) : null
	);

	const endDateTime = $derived.by(() =>
		draftEndDate ? combine(draftEndDate, draftEndTime) : null
	);

	const startsAtIso = $derived(startDateTime ? startDateTime.toISOString() : null);
	const endsAtIso = $derived(endDateTime ? endDateTime.toISOString() : null);

	const durationLabel = $derived.by(() => {
		if (!startDateTime || !endDateTime) return null;
		const ms = endDateTime.getTime() - startDateTime.getTime();
		if (ms <= 0) return null;
		const totalMinutes = Math.round(ms / 60000);
		const days = Math.floor(totalMinutes / 1440);
		const hours = Math.floor((totalMinutes % 1440) / 60);
		const minutes = totalMinutes % 60;
		const parts: string[] = [];
		if (days > 0) parts.push(`${days}d`);
		if (hours > 0) parts.push(`${hours}h`);
		if (minutes > 0 && days === 0) parts.push(`${minutes}m`);
		return parts.join(' ') || '0m';
	});

	const crossesMidnight = $derived.by(() => {
		if (!draftStartDate || !draftEndDate) return false;
		return daysBetween(draftStartDate, draftEndDate) > 0;
	});

	function onStartDateChange(d: Date | null) {
		const prev = draftStartDate;
		draftStartDate = d;
		if (!d) return;
		if (!draftEndDate) {
			draftEndDate = d;
			return;
		}
		if (prev) {
			const offset = daysBetween(prev, draftEndDate);
			draftEndDate = addDays(d, Math.max(0, offset));
		} else if (draftEndDate.getTime() < d.getTime()) {
			draftEndDate = d;
		}
		bumpEndIfOverlap();
	}

	function onEndDateChange(d: Date | null) {
		draftEndDate = d;
	}

	function onStartTimeChange(v: string) {
		draftStartTime = v;
		bumpEndIfOverlap();
	}

	function onEndTimeChange(v: string) {
		draftEndTime = v;
		bumpEndIfOverlap();
	}

	function bumpEndIfOverlap() {
		if (!draftStartDate || !draftEndDate) return;
		if (daysBetween(draftStartDate, draftEndDate) !== 0) return;
		if (timeToMinutes(draftEndTime) <= timeToMinutes(draftStartTime)) {
			draftEndDate = addDays(draftStartDate, 1);
		}
	}

	function startEditing() {
		editing = true;
		localError = null;
		const startSeed = event?.starts_at
			? new Date(event.starts_at)
			: new Date(Date.now() + 30 * 60 * 1000);
		const endSeed = event?.ends_at
			? new Date(event.ends_at)
			: new Date(startSeed.getTime() + 2 * 60 * 60 * 1000);
		draftStartDate = stripTime(startSeed);
		draftEndDate = stripTime(endSeed);
		draftStartTime = formatTimeFromDate(startSeed);
		draftEndTime = formatTimeFromDate(endSeed);
	}

	function cancelEditing() {
		editing = false;
		localError = null;
	}

	function validateDraft(): string | null {
		if (!draftStartDate) return 'Please pick a start date.';
		if (!draftEndDate) return 'Please pick an end date.';
		if (!startsAtIso || !endsAtIso) return 'Please pick start and end times.';
		const startMs = new Date(startsAtIso).getTime();
		const endMs = new Date(endsAtIso).getTime();
		if (endMs <= startMs) return 'End must be after the start.';
		if (startMs <= Date.now()) return 'Start must be in the future.';
		return null;
	}

	function onSubmit(submitEvent: SubmitEvent) {
		const err = validateDraft();
		if (err) {
			submitEvent.preventDefault();
			localError = err;
		} else {
			localError = null;
		}
	}

	function fmtFull(iso: string): string {
		try {
			return new Intl.DateTimeFormat(undefined, {
				weekday: 'short',
				day: 'numeric',
				month: 'short',
				year: 'numeric',
				hour: '2-digit',
				minute: '2-digit'
			}).format(new Date(iso));
		} catch {
			return iso;
		}
	}

	function fmtTime(iso: string): string {
		try {
			return new Intl.DateTimeFormat(undefined, {
				hour: '2-digit',
				minute: '2-digit'
			}).format(new Date(iso));
		} catch {
			return iso;
		}
	}

	function sameDay(a: string, b: string): boolean {
		const da = new Date(a);
		const db = new Date(b);
		return (
			da.getFullYear() === db.getFullYear() &&
			da.getMonth() === db.getMonth() &&
			da.getDate() === db.getDate()
		);
	}

	const startsAtFormatted = $derived(event ? fmtFull(event.starts_at) : '');
	const endsAtFormatted = $derived(
		event
			? sameDay(event.starts_at, event.ends_at)
				? fmtTime(event.ends_at)
				: fmtFull(event.ends_at)
			: ''
	);

	let now = $state(new Date());

	$effect(() => {
		const id = setInterval(() => {
			now = new Date();
		}, 1000);
		return () => clearInterval(id);
	});

	const countdown = $derived.by(() => {
		if (!event) return '';
		const startMs = new Date(event.starts_at).getTime();
		const endMs = new Date(event.ends_at).getTime();
		const t = now.getTime();
		if (t >= endMs) return 'ENDED';
		if (t >= startMs) {
			const diff = Math.floor((endMs - t) / 1000);
			return `IN PROGRESS — ${formatDelta(diff)} LEFT`;
		}
		const diff = Math.floor((startMs - t) / 1000);
		return `STARTS IN ${formatDelta(diff)}`;
	});

	function formatDelta(seconds: number): string {
		const days = Math.floor(seconds / 86400);
		const hours = Math.floor((seconds % 86400) / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const secs = seconds % 60;
		const pad = (n: number) => n.toString().padStart(2, '0');
		if (days > 0) return `${days}d ${pad(hours)}:${pad(minutes)}:${pad(secs)}`;
		return `${pad(hours)}:${pad(minutes)}:${pad(secs)}`;
	}

	const rosterEntries = $derived.by(() => {
		const rsvpByAddr: Record<string, RsvpEntry> = {};
		for (const r of event?.rsvps ?? []) {
			rsvpByAddr[r.address.toLowerCase()] = r;
		}
		return members.map((m) => {
			const found = rsvpByAddr[m.address.toLowerCase()];
			return {
				address: m.address,
				username: m.username ?? found?.username ?? shortAddr(m.address),
				status: found?.status ?? null
			};
		});
	});

	const rsvpCounts = $derived.by(() => {
		const counts = { present: 0, maybe: 0, absent: 0, none: 0 };
		for (const entry of rosterEntries) {
			if (entry.status === 'present') counts.present += 1;
			else if (entry.status === 'maybe') counts.maybe += 1;
			else if (entry.status === 'absent') counts.absent += 1;
			else counts.none += 1;
		}
		return counts;
	});

	function shortAddr(addr: string): string {
		if (addr.length <= 10) return addr;
		return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
	}

	function statusLabel(status: RsvpStatus | null): string {
		if (status === 'present') return 'Present';
		if (status === 'absent') return 'Absent';
		if (status === 'maybe') return 'Maybe';
		return 'No Response';
	}

	const errorToShow = $derived(localError ?? formError ?? null);
</script>

<section class="event-panel">
	<SectionTitle title="Scheduled Event" size="small" tone="gold">
		{#if event}
			<span class="trail-countdown">{countdown}</span>
		{/if}
	</SectionTitle>

	{#if errorToShow}
		<p class="error-msg">{errorToShow}</p>
	{/if}

	{#if !event && !editing}
		<div class="empty">
			{#if isCreator}
				<p class="empty-text">No event scheduled. Pick a moment for the warband.</p>
				<OrnateButton variant="primary" size="sm" onclick={startEditing}>
					Schedule Event
				</OrnateButton>
			{:else}
				<p class="empty-text">No event scheduled yet. The room creator can pick a time.</p>
			{/if}
		</div>
	{/if}

	{#if event && !editing}
		<div class="event-meta">
			<div class="event-time">
				<span class="time-value small-caps">{startsAtFormatted}</span>
				<span class="time-end">→ ends {endsAtFormatted}</span>
			</div>
			{#if isCreator}
				<div class="creator-actions">
					<OrnateButton variant="secondary" size="sm" onclick={startEditing}>
						Reschedule
					</OrnateButton>
					<form method="POST" action="?/cancelEvent" use:enhance class="inline-form">
						<OrnateButton variant="danger" size="sm" type="submit">Cancel Event</OrnateButton>
					</form>
				</div>
			{/if}
		</div>

		{#if isMember}
			<div class="rsvp-controls">
				<span class="micro-label small-caps">Your RSVP</span>
				<div class="rsvp-buttons">
					{#each ['present', 'maybe', 'absent'] as status (status)}
						<form method="POST" action="?/setRsvp" use:enhance class="rsvp-form">
							<input type="hidden" name="status" value={status} />
							<button
								type="submit"
								class="rsvp-btn small-caps"
								class:active={myRsvp?.status === status}
								data-status={status}
							>
								{statusLabel(status as RsvpStatus)}
							</button>
						</form>
					{/each}
				</div>
			</div>
		{/if}

		<div class="roster">
			<span class="micro-label small-caps">RSVP Roster</span>
			<div class="rsvp-summary">
				<span class="summary-pill small-caps" data-status="present">
					<span class="dot"></span>
					{rsvpCounts.present} Present
				</span>
				<span class="summary-pill small-caps" data-status="maybe">
					<span class="dot"></span>
					{rsvpCounts.maybe} Maybe
				</span>
				<span class="summary-pill small-caps" data-status="absent">
					<span class="dot"></span>
					{rsvpCounts.absent} Absent
				</span>
				<span class="summary-pill small-caps" data-status="none">
					<span class="dot"></span>
					{rsvpCounts.none} No Response
				</span>
			</div>
			{#if rosterEntries.length === 0}
				<p class="empty-text">No members yet.</p>
			{:else}
				<ul class="roster-list">
					{#each rosterEntries as entry (entry.address)}
						<li class="roster-row" data-status={entry.status ?? 'none'}>
							<span class="roster-name small-caps">{entry.username}</span>
							<span class="roster-status small-caps">{statusLabel(entry.status)}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	{/if}

	{#if editing}
		<form
			method="POST"
			action="?/scheduleEvent"
			class="schedule-form"
			onsubmit={onSubmit}
			use:enhance={() => {
				return async ({ update, result }) => {
					await update();
					if (result.type === 'success') {
						editing = false;
					}
				};
			}}
		>
			<input type="hidden" name="starts_at" value={startsAtIso ?? ''} />
			<input type="hidden" name="ends_at" value={endsAtIso ?? ''} />

			<div class="schedule-grid">
				<div class="field group-label start-label">
					<span class="micro-label small-caps">Start</span>
				</div>
				<div class="field date-field start-date">
					<D2DatePicker
						value={draftStartDate}
						onChange={onStartDateChange}
						min={todayStart}
						placeholder="Pick a date"
						ariaLabel="Start date"
					/>
				</div>
				<div class="field time-field start-time">
					<D2TimePicker
						value={draftStartTime}
						onChange={onStartTimeChange}
						ariaLabel="Start time"
					/>
				</div>

				<div class="field group-label end-label">
					<span class="micro-label small-caps">
						End
						{#if durationLabel}
							<span class="duration-badge">{durationLabel}</span>
						{:else if crossesMidnight}
							<span class="duration-badge">overnight</span>
						{/if}
					</span>
				</div>
				<div class="field date-field end-date">
					<D2DatePicker
						value={draftEndDate}
						onChange={onEndDateChange}
						min={endMinDate}
						placeholder="Pick a date"
						ariaLabel="End date"
					/>
				</div>
				<div class="field time-field end-time">
					<D2TimePicker value={draftEndTime} onChange={onEndTimeChange} ariaLabel="End time" />
				</div>
			</div>

			<div class="schedule-actions">
				<OrnateButton variant="primary" size="sm" type="submit">Save</OrnateButton>
				<OrnateButton variant="ghost" size="sm" onclick={cancelEditing}>Cancel</OrnateButton>
			</div>
		</form>
	{/if}
</section>

<style>
	.event-panel {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
		padding: 0.85rem 1rem 0.95rem;
		background: linear-gradient(180deg, var(--stone-2) 0%, var(--stone-1) 100%);
		border: 1px solid var(--stone-5);
		box-shadow:
			var(--bevel-in),
			inset 0 0 30px rgba(0, 0, 0, 0.25);
		/* Cap the whole event area so a full lobby's RSVP list scrolls here
		   instead of growing the panel and squeezing the chat out of view. */
		max-height: clamp(180px, 32vh, 320px);
		overflow-y: auto;
	}

	.trail-countdown {
		font-family: var(--font-mono);
		font-size: 0.7rem;
		color: var(--gold-base);
		letter-spacing: 0.1em;
	}

	.error-msg {
		margin: 0;
		padding: 0.55rem 0.8rem;
		border: 1px solid #4a1414;
		background: rgba(181, 54, 54, 0.08);
		color: var(--blood-bright);
		font-family: var(--font-mono);
		font-size: 0.75rem;
		letter-spacing: 0.05em;
	}

	.empty {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		align-items: flex-start;
		padding: 0.35rem 0;
	}

	.empty-text {
		margin: 0;
		font-family: var(--font-display);
		font-size: 0.82rem;
		color: var(--bone-dim);
		letter-spacing: 0.02em;
		font-style: italic;
	}

	.event-meta {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.7rem;
	}

	.event-time {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.time-value {
		font-family: var(--font-display);
		font-size: 1rem;
		color: var(--bone-bright);
		letter-spacing: var(--track-loose);
	}

	.time-end {
		font-family: var(--font-mono);
		font-size: 0.7rem;
		color: var(--bone-dim);
		letter-spacing: 0.06em;
	}

	.creator-actions {
		display: flex;
		gap: 0.45rem;
		flex-wrap: wrap;
	}

	.inline-form {
		display: contents;
	}

	.rsvp-controls,
	.roster {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.micro-label {
		font-family: var(--font-display);
		font-size: 0.65rem;
		color: var(--bone-dim);
		letter-spacing: var(--track-loose);
	}

	.rsvp-buttons {
		display: flex;
		gap: 0.45rem;
		flex-wrap: wrap;
	}

	.rsvp-form {
		flex: 1;
		min-width: 110px;
		display: contents;
	}

	.rsvp-btn {
		flex: 1;
		min-width: 110px;
		background: #080604;
		border: 1px solid var(--stone-5);
		color: var(--bone-dim);
		padding: 0.5rem 0.8rem;
		font-family: var(--font-display);
		font-size: 0.72rem;
		letter-spacing: var(--track-loose);
		cursor: pointer;
		transition:
			border-color 140ms ease,
			color 140ms ease,
			background 140ms ease,
			box-shadow 140ms ease;
		box-shadow: var(--bevel-in);
	}

	.rsvp-btn:hover:not(:disabled) {
		border-color: var(--gold-muted);
		color: var(--gold-lit);
	}

	.rsvp-btn.active[data-status='present'] {
		border-color: var(--green-base, #6f8f4f);
		color: #0d0d0d;
		background: var(--green-base, #a4ce82);
	}
	.rsvp-btn.active[data-status='maybe'] {
		border-color: var(--gold-base);
		color: #0d0d0d;
		background: var(--gold-base);
	}
	.rsvp-btn.active[data-status='absent'] {
		border-color: #7a1d1d;
		color: #f5e8e8;
		background: #6a1818;
	}

	.rsvp-summary {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-top: 0.15rem;
	}

	.summary-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.3rem 0.65rem;
		background: rgba(0, 0, 0, 0.3);
		border: 1px solid var(--stone-5);
		font-family: var(--font-display);
		font-size: 0.65rem;
		letter-spacing: var(--track-loose);
		color: var(--bone-dim);
	}

	.summary-pill .dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background: var(--stone-5);
		flex-shrink: 0;
	}

	.summary-pill[data-status='present'] .dot {
		background: var(--green-base, #a4ce82);
	}
	.summary-pill[data-status='maybe'] .dot {
		background: var(--gold-base);
	}
	.summary-pill[data-status='absent'] .dot {
		background: #b53636;
	}
	.summary-pill[data-status='none'] .dot {
		background: var(--bone-dim);
		opacity: 0.4;
	}

	.roster-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.roster-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0.55rem;
		border-bottom: 1px solid var(--stone-5);
		font-family: var(--font-display);
		font-size: 0.78rem;
	}

	.roster-row:last-child {
		border-bottom: 0;
	}

	.roster-name {
		color: var(--bone);
		letter-spacing: var(--track-loose);
		/* Truncate long usernames instead of stretching the row. */
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.roster-status {
		font-size: 0.7rem;
		letter-spacing: var(--track-loose);
		flex-shrink: 0;
	}

	.roster-row[data-status='present'] .roster-status {
		color: var(--green-base, #a4ce82);
	}
	.roster-row[data-status='maybe'] .roster-status {
		color: var(--gold-base);
	}
	.roster-row[data-status='absent'] .roster-status {
		color: #b53636;
	}
	.roster-row[data-status='none'] .roster-status {
		color: var(--bone-dim);
		opacity: 0.55;
	}

	.schedule-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.schedule-grid {
		display: grid;
		grid-template-columns: auto minmax(180px, 2fr) minmax(110px, 1fr);
		gap: 0.45rem 0.6rem;
		align-items: center;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		min-width: 0;
	}

	.group-label {
		justify-content: flex-start;
		min-width: 90px;
	}

	.field .micro-label {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: nowrap;
		white-space: nowrap;
	}

	.duration-badge {
		font-family: var(--font-mono);
		font-size: 0.6rem;
		color: var(--gold-base);
		letter-spacing: 0.1em;
		text-transform: uppercase;
		padding: 0.05rem 0.4rem;
		border: 1px solid var(--gold-deep);
		background: rgba(227, 188, 116, 0.08);
		white-space: nowrap;
	}

	.schedule-actions {
		display: flex;
		gap: 0.5rem;
	}

	@media (max-width: 560px) {
		.schedule-grid {
			grid-template-columns: 1fr 1fr;
			gap: 0.45rem;
		}
		.group-label {
			grid-column: 1 / -1;
			justify-content: flex-start;
		}
		.date-field {
			grid-column: 1 / -1;
		}
	}
</style>
