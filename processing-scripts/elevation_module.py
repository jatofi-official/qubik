import rasterio
from typing import List, Tuple

# A brilliant tool that I discovered. I have made this into a separate module because I feel fancy
# Parts of this code are inspired by an AI sample code.
class ElevationLookup:
    def __init__(self, dem_path: str):
        """
        Initializes the elevation engine and opens the GeoTIFF resource.
        """
        self.dem_path = dem_path
        self.src = rasterio.open(self.dem_path)
        
    def get_elevation(self, lat: float, lon: float) -> float:
        """
        Get elevation for a single coordinate point.
        Remember: rasterio expects (Longitude, Latitude) -> (X, Y)
        """
        # Close-up bounds check to prevent silent out-of-bounds 0.0 results
        if not (self.src.bounds.left <= lon <= self.src.bounds.right and 
                self.src.bounds.bottom <= lat <= self.src.bounds.top):
            return None # Or raise ValueError depending on your preference
            
        for val in self.src.sample([(lon, lat)]):
            return float(val[0])

    def close(self):
        """Closes the underlying raster file handling handles."""
        self.src.close()

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()