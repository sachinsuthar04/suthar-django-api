
# Suthar Samaj Backend - Feature-wise Structure

This project is a feature-wise Django REST API for the Suthar Samaj community app.

Apps:
- users  : Member model (members of families)
- families : Family model and transfer endpoints
- community: Event, Notice, Advertisement models (CRUD)
- core : shared settings and router

Authentication: Admins use Django admin + JWT for API access. Members are represented by the Member model (mobile + claim flow can be added later).

Quick start (dev + sqlite):
1. python -m venv venv
2. source venv/bin/activate   (or venv\Scripts\activate on Windows)
3. pip install -r requirements.txt
4. cp .env.example .env
5. python manage.py migrate
6. python manage.py createsuperuser
7. python manage.py runserver

API highlights (default /api/ prefix):
- /api/families/          CRUD families + transfer action
- /api/members/           CRUD members (members belong to families via family_id)
- /api/events/            CRUD events (community)
- /api/notices/           CRUD notices
- /api/ads/               CRUD advertisements
- /api/token/             JWT token obtain (admin)
