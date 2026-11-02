/** One JSON line per log entry; the region agent ships stdout to VictoriaLogs. */
export function logLine(level: 'INFO' | 'WARNING' | 'ERROR', msg: string, fields = {}): void {
	const line = JSON.stringify({
		_time: new Date().toISOString(),
		_msg: msg,
		level,
		logger: 'frontend',
		...fields
	});
	if (level === 'ERROR') console.error(line);
	else console.log(line);
}
