import os
from dotenv import load_dotenv
from openCGaT.components.ProjectPaths import ProjectPaths

load_dotenv(os.path.join(ProjectPaths.BASE_DIR, '.env'))

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

WHITENOISE_MANIFEST_STRICT = False


STATIC_ROOT = os.path.join(ProjectPaths.BASE_DIR, 'static/')
STATIC_URL = '/static/'

# Extra places for collectstatic to find static files.
STATICFILES_DIRS = [
    os.path.join(ProjectPaths.PROJECT_ROOT, 'static'),
    os.path.join(ProjectPaths.BASE_DIR, 'tailwind/static')
]

MEDIA_ROOT = os.path.join(ProjectPaths.BASE_DIR, 'media')
MEDIA_URL = '/media/'

STORAGES ={
    "default": {
        "BACKEND": "images.PublicAzureStorage.PublicAzureStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

AZURE_ACCOUNT_NAME = os.getenv('AZURE_ACCOUNT_NAME')
AZURE_ACCOUNT_KEY = os.getenv('AZURE_ACCOUNT_KEY')
AZURE_CONTAINER = os.getenv('AZURE_CONTAINER')
AZURE_PUBLIC_CONTAINER = os.getenv('AZURE_PUBLIC_CONTAINER')

AWS_ACCESS_KEY_ID = os.getenv('STATIC_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('STATIC_SECRET_KEY')

AWS_STORAGE_BUCKET_NAME = os.getenv('STATIC_BUCKET_NAME')
AWS_S3_ENDPOINT_URL = os.getenv('STATIC_ENDPOINT_URL')

AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
AWS_LOCATION = 'cgtstatic/static'
AWS_DEFAULT_ACL = 'public-read'