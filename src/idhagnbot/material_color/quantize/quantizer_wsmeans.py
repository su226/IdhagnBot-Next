"""
An image quantizer that improves on the speed of a standard K-Means algorithm by
implementing several optimizations, including deduping identical pixels and a triangle
inequality rule that reduces the number of comparisons needed to identify which cluster
a point should be moved to.

Wsmeans stands for Weighted Square Means.

This algorithm was designed by M. Emre Celebi, and was found in their 2011 paper,
Improving the Performance of K-Means for Color Quantization.
https://arxiv.org/abs/1101.0395
"""

import math
import random
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass

from idhagnbot.material_color.color_utils import argb_from_lab, lab_from_argb
from idhagnbot.material_color.math_utils import Vec3f, point_distance

_MAX_ITERATIONS = 10
_MIN_MOVEMENT_DISTANCE = 3.0


@dataclass
class _DistanceAndIndex:
    """A wrapper for maintaining a table of distances between K-Means clusters."""

    distance: float = -1
    index: int = -1


def quantize(
    input_pixels: Iterable[int],
    starting_clusters: list[int],
    max_colors: int,
) -> OrderedDict[int, int]:
    """
    :param input_pixels: Colors in ARGB format.
    :param starting_clusters: Defines the initial state of the quantizer. Passing an
                              empty array is fine, the implementation will create its
                              own initial state that leads to reproducible results for
                              the same inputs. Passing an array that is the result of Wu
                              quantization leads to higher quality results.
    :param max_colors: The number of colors to divide the image into. A lower number of
                       colors may be returned.
    :return: Colors in ARGB format.
    """
    random.seed(69)
    pixel_to_count = OrderedDict[int, int]()
    points: list[Vec3f] = []
    pixels: list[int] = []
    point_count = 0
    for input_pixel in input_pixels:
        if input_pixel not in pixel_to_count:
            point_count += 1
            points.append(lab_from_argb(input_pixel))
            pixels.append(input_pixel)
            pixel_to_count[input_pixel] = 1
        else:
            pixel_to_count[input_pixel] = pixel_to_count[input_pixel] + 1
    counts: list[int] = [
        pixel_to_count[pixel]
        for i in range(point_count)
        if (pixel := pixels[i]) in pixel_to_count
    ]
    cluster_count = min(max_colors, point_count)
    if starting_clusters:
        cluster_count = min(cluster_count, len(starting_clusters))
    clusters = [lab_from_argb(cluster) for cluster in starting_clusters]
    additional_clusters_needed = cluster_count - len(clusters)
    if not starting_clusters and additional_clusters_needed > 0:
        for _ in range(additional_clusters_needed):
            l = random.uniform(0, 1) * 100.0
            a = random.uniform(0, 1) * (100.0 - (-100.0) + 1) + -100
            b = random.uniform(0, 1) * (100.0 - (-100.0) + 1) + -100
            clusters.append((l, a, b))
    cluster_indices: list[int] = [
        math.floor(random.uniform(0, 1) * cluster_count) for _ in range(point_count)
    ]
    index_matrix = [[0 for _ in range(cluster_count)] for _ in range(cluster_count)]
    distance_to_index_matrix = [
        [_DistanceAndIndex() for _ in range(cluster_count)]
        for _ in range(cluster_count)
    ]
    pixel_count_sums: list[int] = [0 for _ in range(cluster_count)]
    for iteration in range(_MAX_ITERATIONS):
        for i in range(cluster_count):
            for j in range(i + 1, cluster_count):
                distance = point_distance(clusters[i], clusters[j])
                distance_to_index_matrix[j][i].distance = distance
                distance_to_index_matrix[j][i].index = i
                distance_to_index_matrix[i][j].distance = distance
                distance_to_index_matrix[i][j].index = j
            for j in range(cluster_count):
                index_matrix[i][j] = distance_to_index_matrix[i][j].index
        points_moved = 0
        for i in range(point_count):
            point = points[i]
            previous_cluster_index = cluster_indices[i]
            previous_cluster = clusters[previous_cluster_index]
            previous_distance = point_distance(point, previous_cluster)
            minimum_distance = previous_distance
            new_cluster_index = -1
            for j in range(cluster_count):
                if (
                    distance_to_index_matrix[previous_cluster_index][j].distance
                    >= 4 * previous_distance
                ):
                    continue
                distance = point_distance(point, clusters[j])
                if distance < minimum_distance:
                    minimum_distance = distance
                    new_cluster_index = j
            if new_cluster_index != -1:
                distance_change = abs(
                    math.sqrt(minimum_distance) - math.sqrt(previous_distance),
                )
                if distance_change > _MIN_MOVEMENT_DISTANCE:
                    points_moved += 1
                    cluster_indices[i] = new_cluster_index
        if points_moved == 0 and iteration != 0:
            break
        component_a_sums = [0.0] * cluster_count
        component_b_sums = [0.0] * cluster_count
        component_c_sums = [0.0] * cluster_count
        for i in range(cluster_count):
            pixel_count_sums[i] = 0
        for i in range(point_count):
            cluster_index = cluster_indices[i]
            point = points[i]
            count = counts[i]
            pixel_count_sums[cluster_index] += count
            component_a_sums[cluster_index] += point[0] * count
            component_b_sums[cluster_index] += point[1] * count
            component_c_sums[cluster_index] += point[2] * count
        for i in range(cluster_count):
            count = pixel_count_sums[i]
            if count == 0:
                clusters[i] = (0, 0, 0)
                continue
            a = component_a_sums[i] / count
            b = component_b_sums[i] / count
            c = component_c_sums[i] / count
            clusters[i] = (a, b, c)
    argb_to_population = OrderedDict[int, int]()
    for i in range(cluster_count):
        count = pixel_count_sums[i]
        if count == 0:
            continue
        possible_new_cluster = argb_from_lab(*clusters[i])
        if possible_new_cluster in argb_to_population:
            continue
        argb_to_population[possible_new_cluster] = count
    return argb_to_population
