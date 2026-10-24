from pydantic import BaseModel
from typing import Optional, List

class ModifierOut(BaseModel):
    id: str
    group_id: str
    name: str
    price: float

class ModifierGroupOut(BaseModel):
    id: str
    name: str
    min_select: int
    max_select: int
    is_required: bool
    modifiers: List[ModifierOut] = []

class MenuItemOut(BaseModel):
    id: str
    category_id: str
    name: str
    description: Optional[str] = None
    price: float
    is_available: bool
    is_kitchen_item: bool
    allergen_tags: Optional[str] = None
    prep_time_mins: int
    modifier_groups: List[ModifierGroupOut] = []

class CategoryOut(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None
    display_order: int
    items: List[MenuItemOut] = []
