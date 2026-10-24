"""
Menu Categories, Items, and Modifiers Endpoints.
"""
from fastapi import APIRouter
from app.database import get_connection
from app.schemas.menu import CategoryOut, MenuItemOut, ModifierGroupOut, ModifierOut

router = APIRouter(prefix="/api/menu", tags=["Menu & Products"])

@router.get("/categories", response_model=list[CategoryOut])
async def get_menu():
    conn = get_connection()
    cursor = conn.cursor()
    
    categories = cursor.execute("SELECT * FROM menu_categories ORDER BY display_order ASC;").fetchall()
    
    cat_list = []
    for cat in categories:
        items = cursor.execute("""
            SELECT * FROM menu_items WHERE category_id = ? ORDER BY price ASC;
        """, (cat["id"],)).fetchall()
        
        item_list = []
        for itm in items:
            # Fetch modifier groups for this item
            groups = cursor.execute("""
                SELECT mg.* FROM modifier_groups mg
                JOIN item_modifier_groups img ON mg.id = img.group_id
                WHERE img.item_id = ?;
            """, (itm["id"],)).fetchall()
            
            group_list = []
            for g in groups:
                mods = cursor.execute("SELECT * FROM modifiers WHERE group_id = ?;", (g["id"],)).fetchall()
                mod_list = [ModifierOut(id=m["id"], group_id=m["group_id"], name=m["name"], price=m["price"]) for m in mods]
                group_list.append(ModifierGroupOut(
                    id=g["id"],
                    name=g["name"],
                    min_select=g["min_select"],
                    max_select=g["max_select"],
                    is_required=bool(g["is_required"]),
                    modifiers=mod_list
                ))
                
            item_list.append(MenuItemOut(
                id=itm["id"],
                category_id=itm["category_id"],
                name=itm["name"],
                description=itm["description"],
                price=itm["price"],
                is_available=bool(itm["is_available"]),
                is_kitchen_item=bool(itm["is_kitchen_item"]),
                allergen_tags=itm["allergen_tags"],
                prep_time_mins=itm["prep_time_mins"],
                modifier_groups=group_list
            ))
            
        cat_list.append(CategoryOut(
            id=cat["id"],
            name=cat["name"],
            icon=cat["icon"],
            display_order=cat["display_order"],
            items=item_list
        ))
        
    conn.close()
    return cat_list

@router.get("/items", response_model=list[MenuItemOut])
async def list_items(available_only: bool = True):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM menu_items"
    if available_only:
        query += " WHERE is_available = 1"
    query += " ORDER BY name ASC;"
    
    rows = cursor.execute(query).fetchall()
    results = [MenuItemOut(
        id=r["id"],
        category_id=r["category_id"],
        name=r["name"],
        description=r["description"],
        price=r["price"],
        is_available=bool(r["is_available"]),
        is_kitchen_item=bool(r["is_kitchen_item"]),
        allergen_tags=r["allergen_tags"],
        prep_time_mins=r["prep_time_mins"],
        modifier_groups=[]
    ) for r in rows]
    
    conn.close()
    return results
