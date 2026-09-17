"""Shallow libvips demand-graph composition helpers."""


def balanced_vertical_join(images):
    level = list(images)
    while len(level) > 1:
        joined = []
        for index in range(0, len(level), 2):
            if index + 1 == len(level):
                joined.append(level[index])
            else:
                joined.append(level[index].join(
                    level[index + 1], "vertical", expand=True,
                    background=[0, 0, 0, 0], align="low",
                ))
        level = joined
    return level[0]
