"""One closed warp cycle per PVD pseudo-time, sampled in real seconds."""


def samples_per_mode(a):
    return max(5, round(a.seconds_per_cycle * a.fps))


def sample(a, index):
    count = samples_per_mode(a)
    mode_index, local = divmod(index, count)
    anchors = [round(q*(count-1)/4) for q in range(5)]
    values = [0, 1, 0, -1, 0]
    for quarter in range(4):
        if local <= anchors[quarter+1]:
            fraction = (local-anchors[quarter])/(anchors[quarter+1]-anchors[quarter])
            scale = a.amplitude*(values[quarter]+fraction*(values[quarter+1]-values[quarter]))
            return a.mode_times[mode_index], scale
    raise IndexError(index)


def frame_count(a):
    return len(a.mode_times)*samples_per_mode(a)


def frame_plan(a):
    unique, aliases, seen = [], [], {}
    for index in range(frame_count(a)):
        mode, scale = sample(a,index)
        key = (mode,round(scale,12))
        if key not in seen:
            seen[key] = index
            unique.append(index)
        aliases.append(seen[key])
    return unique, aliases


def content_size(view_size, output_size):
    scale = min(output_size[0]/view_size[0],output_size[1]/view_size[1])
    return [max(2,2*int(value*scale/2)) for value in view_size]
