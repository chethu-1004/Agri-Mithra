from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from agrinetra.auth.dependencies import get_current_user
from agrinetra.database.connection import get_db
from agrinetra.database.models import MarketListing, MarketOrder, MarketProduct, MarketContact, User
from agrinetra.api.schemas import MarketListingIn, MarketOrderIn
from agrinetra.config import settings

router = APIRouter(prefix='/api/market', tags=['marketplace'])


def product_json(product: MarketProduct) -> dict:
    return {
        'id': product.id, 'name': product.name, 'category': product.category,
        'brand': product.brand, 'description': product.description,
        'price': product.price, 'emoji': product.emoji, 'is_active': product.is_active,
        'image_url': f'/api/market/products/{product.id}/image' if product.image_storage_key else None,
    }


def listing_json(listing: MarketListing, user: User | None = None) -> dict:
    return {
        'id': listing.id, 'user_id': listing.user_id,
        'user_name': user.name if user else None, 'user_email': user.email if user else None,
        'name': listing.crop_name, 'crop_name': listing.crop_name, 'variety': listing.variety,
        'quantity': listing.quantity, 'qty': listing.quantity, 'price': listing.price,
        'harvest': listing.harvest, 'location': listing.location, 'grade': listing.grade,
        'status': listing.status, 'created_at': listing.created_at,
    }


def contact_json(contact: MarketContact) -> dict:
    return {
        'id': contact.id, 'kind': contact.kind, 'name': contact.name,
        'organization': contact.organization, 'interests': contact.interests,
        'phone': contact.phone, 'email': contact.email, 'location': contact.location,
        'description': contact.description, 'is_active': contact.is_active,
    }


@router.get('/products')
def products(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    del user
    rows = db.query(MarketProduct).filter(MarketProduct.is_active.is_(True)).order_by(MarketProduct.created_at.desc()).all()
    return [product_json(row) for row in rows]


@router.get('/contacts')
def contacts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    del user
    rows = db.query(MarketContact).filter(MarketContact.is_active.is_(True)).order_by(MarketContact.created_at.desc()).all()
    return [contact_json(row) for row in rows]


@router.get('/products/{product_id}/image')
def product_image(product_id:str,db:Session=Depends(get_db)):
    product=db.get(MarketProduct,product_id)
    key=product.image_storage_key if product else None
    if not key or Path(key).name!=key:
        raise HTTPException(404,'Product image not found.')
    image_path=Path(settings.upload_dir)/key
    if not image_path.is_file():
        raise HTTPException(404,'Product image is no longer available.')
    return FileResponse(image_path)


@router.post('/listings')
def create_listing(payload: MarketListingIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    listing = MarketListing(user_id=user.id, **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing_json(listing, user)


@router.get('/listings')
def my_listings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(MarketListing).filter(MarketListing.user_id == user.id).order_by(MarketListing.created_at.desc()).all()
    return [listing_json(row, user) for row in rows]


@router.post('/orders')
def place_order(payload: MarketOrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = db.query(MarketProduct).filter(
        MarketProduct.id == payload.product_id,
        MarketProduct.is_active.is_(True),
    ).first()
    if not product:
        raise HTTPException(404, 'This product is no longer available.')
    order = MarketOrder(user_id=user.id, product_id=product.id, quantity=payload.quantity, unit_price=product.price)
    db.add(order)
    db.commit()
    db.refresh(order)
    return {
        'id': order.id, 'product_id': product.id, 'product_name': product.name,
        'quantity': order.quantity, 'unit_price': order.unit_price,
        'total': round(order.unit_price * order.quantity, 2), 'status': order.status,
        'created_at': order.created_at,
    }


@router.get('/orders')
def my_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(MarketOrder, MarketProduct).join(MarketProduct, MarketProduct.id == MarketOrder.product_id).filter(
        MarketOrder.user_id == user.id
    ).order_by(MarketOrder.created_at.desc()).all()
    return [
        {
            'id': order.id, 'product_id': product.id, 'product_name': product.name,
            'quantity': order.quantity, 'unit_price': order.unit_price,
            'total': round(order.unit_price * order.quantity, 2),
            'status': order.status, 'created_at': order.created_at,
        }
        for order, product in rows
    ]
