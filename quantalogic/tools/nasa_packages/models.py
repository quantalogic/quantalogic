"""Data models for NASA API responses."""

from typing import List

from pydantic import BaseModel, Field


class AsteroidDiameter(BaseModel):
    """Asteroid diameter estimates in meters."""
    min_diameter: float = Field(..., alias="estimated_diameter_min")
    max_diameter: float = Field(..., alias="estimated_diameter_max")

class CloseApproach(BaseModel):
    """Close approach data for an asteroid."""
    date: str = Field(..., alias="close_approach_date_full")
    velocity_kph: float = Field(..., alias="relative_velocity.kilometers_per_hour")
    miss_distance_km: float = Field(..., alias="miss_distance.kilometers")

class Asteroid(BaseModel):
    """Model for asteroid data."""
    name: str
    nasa_jpl_url: str
    is_hazardous: bool = Field(..., alias="is_potentially_hazardous_asteroid")
    diameter: AsteroidDiameter = Field(..., alias="estimated_diameter.meters")
    approaches: List[CloseApproach] = Field(..., alias="close_approach_data")

    def format_info(self) -> str:
        """Format asteroid information into readable text."""
        lines = [
            f"Name: {self.name}",
            f"NASA JPL URL: {self.nasa_jpl_url}",
            f"Potentially Hazardous: {self.is_hazardous}",
            f"Estimated Diameter:",
            f"  Min: {self.diameter.min_diameter:.2f} meters",
            f"  Max: {self.diameter.max_diameter:.2f} meters"
        ]
        
        if self.approaches:
            approach = self.approaches[0]
            lines.extend([
                "\nClosest Approach:",
                f"  Date: {approach.date}",
                f"  Velocity: {approach.velocity_kph} km/h",
                f"  Miss Distance: {approach.miss_distance_km} km"
            ])
        
        return "\n".join(lines)
