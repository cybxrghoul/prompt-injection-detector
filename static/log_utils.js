export function logDetectionToBackend({prompt, overallRisk, blocked, patterns, topFinding}) {
    fetch('/log_detection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            prompt,
            overallRisk,
            blocked,
            patterns,
            topFinding
        })
    });
}
