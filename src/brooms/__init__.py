"""Book University of Bath study rooms (bath.libcal.com) from Python."""

from .client import Brooms, BroomsError, LoginError
from .models import Booking, Slot, Space

__all__ = ["Booking", "Brooms", "BroomsError", "LoginError", "Slot", "Space"]
__version__ = "0.1.1"
