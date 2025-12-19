from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List

from .models import Case, CaseCreate

class CaseStore(ABC):
    @abstractmethod
    def create_case(self, data: CaseCreate) -> Case: ...

    @abstractmethod
    def list_cases(self, status: Optional[str] = None, limit: int = 200) -> List[Case]: ...

    @abstractmethod
    def get_case(self, case_id: int) -> Optional[Case]: ...

    @abstractmethod
    def find_resolved_by_key(
        self,
        brand: str,
        model: str,
        series: Optional[str],
        error_code: Optional[str],
    ) -> Optional[Case]: ...
    @abstractmethod
    def update_status(self, case_id: int, status: str) -> Optional[Case]: ...
