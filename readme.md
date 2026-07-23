.env file structure:

DATABASE_URL=your_postgrese_db_url

LOG_DIR=logs
LOG_LEVEL=INFO
LOG_JSON=false
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

MAX_FILE_SIZE_MB=20

ALLOWED_ORIGINS=http://localhost:3000,http://192.168.8.70:5173,http://localhost:5173

SECRET_KEY=your_own_secret_key

ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=30
