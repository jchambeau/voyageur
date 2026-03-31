# Voyageur

Sailing route planner for the Norman coast.

Computes tidal-aware passage plans step by step — position, heading, SOG, tidal current and safety flags — displayed as an 80-column ASCII timeline.

## Prerequisites

System libraries required by `pyproj` and `shapely`:

```bash
# Arch / Manjaro
sudo pacman -S proj geos

# Debian / Ubuntu
sudo apt install libproj-dev libgeos-dev
```

## Installation

```bash
pip install poetry
poetry install
```

## Usage

### Plan a passage

```bash
poetry run voyageur plan --from Cherbourg --to Granville --depart 2026-03-29T08:00 --wind 240/15
```

Options:

| Option | Description | Default |
|---|---|---|
| `--from` | Departure port or `latN/lonW` | required |
| `--to` | Destination port or `latN/lonW` | required |
| `--depart` | Departure time (ISO 8601) | required |
| `--wind` | Wind direction/speed, e.g. `240/15` | required |
| `--step` | Time step in minutes: 1, 5, 15, 30, 60 | 15 |
| `--draft` | Override saved boat draft (m) | from profile |
| `--max-wind` | Safety threshold: max wind speed (kn) | none |
| `--max-current` | Safety threshold: max tidal current (kn) | none |

Named ports: `Cherbourg`, `Granville`, `Le Havre`, `Saint-Malo`, `Barfleur`, `Saint-Vaast-la-Hougue`, `Honfleur`.

### Manage boat profile

```bash
# Create / update profile
voyageur config --name "Mon Bateau" --loa 12.5 --draft 1.8 --sail-area 65 --default-step 15

# Display saved profile
voyageur config --show
```

Profile is saved to `~/.voyageur/boat.yaml` and loaded automatically for every `plan` run.

## Development

```bash
poetry run pytest tests/ -v            # run tests
poetry run ruff check voyageur/ tests/ # lint
```
