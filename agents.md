# Agent Instructions

## Environment Setup & Execution

### Node.js & Frontend Build
- **Node Environment**: Node.js is managed through NVM located at `~/.nvm`. Before executing `node`, `npm`, or `yarn` commands in subshells or fresh bash sessions, load the NVM environment:
  ```bash
  source ~/.nvm/nvm.sh && nvm use 18
  ```
- **Building Frontend Workspaces**:
  ```bash
  yarn run build-workspaces
  # or
  yarn run build
  ```
- **Watching for Changes**:
  ```bash
  yarn run watch-workspaces
  ```

### Python & Django Backend
- **Python Environment**: The virtual environment is located at `.venv`. Activate it or run directly with:
  ```bash
  source .venv/bin/activate
  ```
- **Running Tests**:
  ```bash
  python manage.py test
  ```
- **Running Migrations & Commands**:
  ```bash
  python manage.py migrate
  python manage.py runserver
  ```

## Partner Toolbar
New management pages should be added to the partner toolbar in `partner/templates/snippets/partner_toolbar.html` to ensure they are easily accessible to partners.
