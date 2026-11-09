from pathlib import Path
from typing import Protocol
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from agrinetra.config import settings
ALLOWED={'image/jpeg','image/png','image/webp'}
class StorageProvider(Protocol):
    async def save(self, upload: UploadFile) -> tuple[str,str]: ...
class LocalStorage:
    async def save(self, upload: UploadFile):
        if upload.content_type not in ALLOWED: raise HTTPException(415,'Upload a JPEG, PNG, or WebP image.')
        limit=settings.max_upload_mb*1024*1024; data=await upload.read(limit+1)
        if not data: raise HTTPException(400,'The uploaded image is empty.')
        if len(data)>limit: raise HTTPException(413,f'Image must be no larger than {settings.max_upload_mb} MB.')
        try:
            from io import BytesIO
            with Image.open(BytesIO(data)) as im:
                if im.width*im.height>40_000_000: raise HTTPException(413,'Image dimensions are too large.')
                im.verify()
        except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError): raise HTTPException(400,'The uploaded image is invalid or corrupted.')
        ext={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[upload.content_type]
        root=Path(settings.upload_dir); root.mkdir(parents=True,exist_ok=True)
        name=f'{uuid4().hex}{ext}'; (root/name).write_bytes(data)
        return str(root/name), name
def get_storage() -> StorageProvider:
    if settings.storage_provider=='local': return LocalStorage()
    raise HTTPException(503,f'Storage provider {settings.storage_provider!r} is configured but no adapter is installed.')
def storage_health(): return {'provider':settings.storage_provider,'ready':settings.storage_provider=='local'}
async def save_image(upload:UploadFile): return await get_storage().save(upload)
