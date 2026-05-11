from abc import ABC, abstractmethod
from typing import List, Optional, Any

class BasePressureController(ABC):
    """Abstract base class for pressure controllers."""
    
    @abstractmethod
    def initialize(self) -> Any:
        """Initialize connection and calibration."""
        pass

    @abstractmethod
    def set_pressure(self, p1: Optional[float] = None, p2: Optional[float] = None, p3: Optional[float] = None, p4: Optional[float] = None):
        """Set pressure targets asynchronously."""
        pass

    @abstractmethod
    def get_pressure_readings(self) -> List[float]:
        """Synchronously get actual pressure readings."""
        pass
        
    @abstractmethod
    def get_target_pressures(self) -> List[float]:
        """Get the current target pressures (state)."""
        pass
