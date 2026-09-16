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

## Partner Management Pages
Management pages for partners should follow these conventions:
- **URL Pattern**: Include `partner/<slug:partner_slug>/` in the URL path.
- **View Logic**: Use `partner.models.get_partner_or_401(request, partner_slug)` to retrieve the partner object and verify the user has access.
- **Template Context**: Always include `'partner': partner` in the template context. This is required for the partner toolbar and other navigation elements to function correctly.
- **Toolbar Integration**: Add new management pages to the partner toolbar in `partner/templates/snippets/partner_toolbar.html`.
  
## Preferred Coding Patterns

### Datetime Handling
Across the project, use the module-prefix pattern for `datetime` and its components:
- **Imports**: Always use `import datetime` instead of `from datetime import ...`.
- **Usage**: Use the full module path for calls, e.g., `datetime.datetime.now()`, `datetime.date.today()`, `datetime.timedelta(days=1)`, and `datetime.datetime.strptime()`.
- **Note**: This pattern ensures consistency and avoids name collisions with variables named `date` or `time`.
