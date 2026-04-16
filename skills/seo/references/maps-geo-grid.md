<!-- Updated: 2026-03-23 -->
# Geo-Grid Rank Tracking Algorithm

## Concept

Geo-grid rank tracking simulates Google Maps searches from multiple GPS
coordinates around a business to show how rankings vary across a geographic
area. The output is a heatmap revealing where the business ranks well (green)
and where competitors dominate (red).

---

## Grid Generation (Haversine-Based)

### Algorithm

1. Take center coordinates (business location): `center_lat`, `center_lng`
2. Define grid size (e.g., 7x7 = 49 points) and radius in km
3. Calculate spacing: `step = (2 * radius_km) / (grid_size - 1)`
4. Generate grid points using offset formula:

```
For each row i (0 to grid_size-1) and column j (0 to grid_size-1):
  dy = (i - center_index) * step_km
  dx = (j - center_index) * step_km
  new_lat = center_lat + (dy / 111.32)
  new_lng = center_lng + (dx / (111.32 * cos(center_lat * pi/180)))
```

Where `center_index = (grid_size - 1) / 2` and `111.32 km = 1 degree latitude`.

### Grid Sizes and Use Cases

| Grid | Points | Typical Radius | Best For | Est. Cost (Live) |
|------|--------|---------------|----------|-----------------|
| 3x3 | 9 | 2 km | Quick snapshot, low budget | $0.018/keyword |
| 5x5 | 25 | 3 km | Standard urban audit | $0.050/keyword |
| **7x7** | **49** | **5 km** | **Default. Best balance of coverage and cost** | **$0.098/keyword** |
| 9x9 | 81 | 8 km | Suburban/wide service area | $0.162/keyword |
| 13x13 | 169 | 15 km | Rural or large metro | $0.338/keyword |

**Radius guidelines:** Urban dense = 2-5 km, suburban = 5-10 km, rural = 10-25 km.

---

## DataForSEO Integration

Use the Google Maps SERP API with `location_coordinate` parameter:

```json
{
  "keyword": "dentist",
  "location_coordinate": "30.2672,-97.7431,15z",
  "language_code": "en",
  "device": "mobile",
  "depth": 20
}
```

For each grid point, fire one API call with the point's lat/lng. Parse the
`items` array to find the target business rank (position in results).

**Rate optimization:** DataForSEO allows up to 100 tasks per POST. For a 7x7
grid, batch all 49 tasks into a single request to minimize HTTP overhead.

---

## Share of Local Voice (SoLV)

Metric pioneered by Local Falcon. Measures visibility across the grid.

### Calculation

```
SoLV = (points_in_top_3 / total_grid_points) * 100
```

### Interpretation

| SoLV | Interpretation |
|------|---------------|
| 80-100% | Dominant. Business owns the local area. |
| 60-79% | Strong. Visible in most of the service area. |
| 40-59% | Moderate. Significant gaps in coverage. |
| 20-39% | Weak. Competitors dominate most areas. |
| 0-19% | Critical. Nearly invisible in maps results. |

### Extended Metrics

- **Average Rank**: Mean position across all grid points (lower = better)
- **Visibility Score**: Weighted average where top 3 = 3pts, 4-10 = 1pt, 10+ = 0pts
- **Worst Quadrant**: Identify which compass direction has weakest rankings

---

## ASCII Heatmap Rendering

For terminal/Markdown output, render a grid using rank-position symbols:

### Format

```
Geo-Grid: "dentist" (7x7, 5km radius, center: 30.267, -97.743)

     W -------- E
  N  1  1  2  3  5  8  -
  |  1  1  1  2  3  6  9
  |  2  1  [1] 1  2  4  7
  |  3  2  1  1  1  3  5
  |  5  3  2  1  2  4  8
  |  8  5  3  2  3  6  -
  S  -  8  5  4  5  9  -

Legend: [1]=center, 1-3=top 3 (strong), 4-10=visible, -=not ranked
SoLV: 57% (28/49 grid points in top 3)
Avg Rank: 3.4 | Weakest: NE quadrant (avg rank 7.2)
```

### Color Mapping (for enhanced output)

| Position | Symbol | Meaning |
|----------|--------|---------|
| 1 | `1` | #1 ranking (best) |
| 2-3 | `2`, `3` | Top 3 (strong local presence) |
| 4-10 | `4`-`9` | Visible but not dominant |
| 11-20 | `+` | Buried in results |
| Not found | `-` | Not ranking at this point |

---

## Multi-Keyword Grid

For comprehensive analysis, scan 2-3 keywords on the same grid:

1. Primary service keyword (e.g., "dentist")
2. Brand + location (e.g., "Smith Dental Austin")
3. Long-tail intent (e.g., "emergency dentist near me")

**Cost for 3-keyword 7x7 scan:** 147 API calls = ~$0.29 (live) or ~$0.088 (standard)

---

## Cost Warning Template

Before running a geo-grid scan, display:

```
Geo-Grid Scan Estimate:
  Grid: 7x7 (49 points)
  Keywords: 3
  API calls: 147
  Estimated cost: $0.09 (standard) - $0.29 (live)
  Proceed? [DataForSEO credits will be consumed]
```
