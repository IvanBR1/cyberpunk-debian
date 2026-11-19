"""Estado MPRIS y reconciliación posterior a controles multimedia."""
import time

SEPARATOR = '\x1f'


def parse_metadata(raw):
    fields = raw.split(SEPARATOR)
    if len(fields) != 5 or not fields[0]:
        return None
    title, artist, status, position, length = fields
    try:
        current = float(position) / 1e6
        duration = float(length) / 1e6
    except ValueError:
        current = duration = None
    return {
        'raw': raw, 'title': title, 'artist': artist, 'status': status,
        'current': current, 'duration': duration,
    }


def settle_metadata(action, before, execute, fetch, pause=time.sleep, attempts=5):
    """Ejecuta un control y espera brevemente a que MPRIS publique el nuevo estado."""
    previous = parse_metadata(before)
    if execute() is False:
        return before
    latest = ''
    for attempt in range(attempts):
        latest = fetch()
        current = parse_metadata(latest)
        if current:
            if action == 'play-pause':
                if not previous or current['status'] != previous['status']:
                    return latest
            elif not previous or (current['title'],current['artist'],current['duration']) != (previous['title'],previous['artist'],previous['duration']):
                return latest
        elif previous:
            return latest
        if attempt + 1 < attempts:
            pause(.12)
    return latest
