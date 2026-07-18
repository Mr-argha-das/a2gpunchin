from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.security import decode_token
from app.models.user import User
from app.services.access_control import access_level_for_user, modules_for_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def authenticated_user(request: Request) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_token(token)
    except ValueError:
        return None
    return User.objects(id=payload.get("sub"), is_active=True).first()


def require_web_login(request: Request):
    user = authenticated_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return user


@router.get("/")
def home(request: Request):
    user = require_web_login(request)
    if isinstance(user, RedirectResponse):
        return user
    access_level = access_level_for_user(user)
    modules = modules_for_user(user)
    return templates.TemplateResponse("dashboard/index.html", {"request": request, "title": "Dashboard", "user": user, "access_level": access_level, "modules": modules})


@router.get("/login")
def login_page(request: Request):
    if authenticated_user(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("auth/login.html", {"request": request, "title": "Login"})


@router.get("/{page_name}")
def page(request: Request, page_name: str):
    user = require_web_login(request)
    if isinstance(user, RedirectResponse):
        return user
    allowed = {"companies", "branches", "departments", "employees", "assets", "attendance", "leave", "reports", "settings", "shifts"}
    access_level = access_level_for_user(user)
    modules = modules_for_user(user)
    if access_level != "admin":
        allowed = set()
        module_pages = {
            "assets": "assets",
            "employees": "employees",
            "attendance": "attendance",
            "leaves": "leave",
            "reports": "reports",
            "branches": "branches",
            "departments": "departments",
            "shifts": "shifts",
        }
        allowed = {page for module, page in module_pages.items() if module in modules}
        if not allowed:
            allowed = {"attendance"}
    if page_name not in allowed:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return templates.TemplateResponse(f"{page_name}/index.html", {"request": request, "title": page_name.title(), "user": user, "access_level": access_level, "modules": modules})
