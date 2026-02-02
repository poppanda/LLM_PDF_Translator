"""
OCR Engine Base Class.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any


class OCRBase(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    def init(self, cfg: dict):
        """
        Initialize OCR engine with configuration.

        Parameters
        ----------
        cfg : dict
            Configuration dictionary
        """
        pass

    @abstractmethod
    def get_text(
        self, image
    ) -> Tuple[Optional[List], Optional[List], Dict[str, float]]:
        """
        Perform OCR on a single image.

        Parameters
        ----------
        image : np.ndarray
            Input image (BGR format)

        Returns
        -------
        Tuple containing:
            - boxes: List of detected text boxes or None
            - texts: List of (text, confidence) tuples or None
            - time_dict: Processing time for each stage
        """
        pass

    @abstractmethod
    def get_all_text(self, layout) -> Any:
        """
        Extract text from all layout elements.

        Parameters
        ----------
        layout : list
            List of layout elements

        Returns
        -------
        layout : list
            Updated layout with extracted text
        """
        pass
