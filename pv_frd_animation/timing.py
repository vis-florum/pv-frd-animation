"""Animation time in seconds, independent of the output sampling rate."""


def duration(a):
    return a.cycles / a.speed


def frame_count(a):
    # Retain the closing zero-displacement pose; encoding adds one endpoint frame.
    return max(1, round(duration(a) * a.fps)) + 1


def frame_time(a, index):
    return duration(a) * index / (frame_count(a) - 1)


def displacement(a, seconds):
    phase = (seconds * a.speed) % 1.0
    level = 4*phase if phase <= 0.25 else (2-4*phase if phase <= 0.75 else 4*phase-4)
    return a.amplitude * level
