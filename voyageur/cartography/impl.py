import importlib.resources
import json

from shapely.geometry import LineString, shape

from voyageur.models import Waypoint


class GeoJsonCartography:
    """CartographyProvider backed by the embedded normandy.geojson file."""

    def __init__(self) -> None:
        self._polygons = self._load_polygons()

    def _load_polygons(self) -> list:
        """Load all polygon geometries from embedded GeoJSON."""
        ref = (
            importlib.resources.files("voyageur.cartography")
            / "data"
            / "normandy.geojson"
        )
        with ref.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [
            shape(feature["geometry"])
            for feature in data["features"]
            if feature.get("geometry")
        ]

    def intersects_land(self, route: list[Waypoint]) -> bool:
        """Return True if any route segment crosses a land or shallow-water polygon."""
        if len(route) < 2:
            return False
        for a, b in zip(route[:-1], route[1:]):
            segment = LineString([(a.lon, a.lat), (b.lon, b.lat)])
            for polygon in self._polygons:
                if segment.intersects(polygon):
                    return True
        return False
