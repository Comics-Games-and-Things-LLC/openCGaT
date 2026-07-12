## Development of `openCGaT`

This is a Django project.

### 1. Install dependencies

Install Python 3, Node 16, and Yarn. Have access to a pSQL database.

### 2. Install all python dependencies.

Install the remaining dependencies:

```sh
pip install -r requirements.txt
yarn
```
#### 2B: If you wish to read invoices
Install additional dependencies:

```sh
pip install opencv-python
```

### 3. Setup local `.env` file.

Copy the example file, and fill in with API keys from the various services.

```sh
cp .env.example .env
```

### 4. Compile Javascript
Do not copy-static without python properly configured (eg node docker container)
```sh
yarn install
yarn watch
```

### 5. Apply migrations

```sh
python manage.py migrate
```

### 6. Generate a local admin account

```sh
python manage.py createsuperuser
```

### 7. Run dev server

```sh
python manage.py runserver
```

### 8. Run dev server

Through the admin ui (url:8000/admin) add a partner, otherwise pages won't be able to serialize the cart.
Through the CMS (url:8000/cms) add a homepage.

