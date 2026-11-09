"""Guarda das rotas públicas do Traefik em produção (docker-compose.prod.yml).

Decisão (nov/2026): o portal das empresas (/empresas) sai de trás do BasicAuth
compartilhado — empresa real entra só com o login do Django (allauth, com
bloqueio após 5 senhas erradas). O BasicAuth continua só no /admin.
"""

import re
from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

COMPOSE_PROD = Path(settings.BASE_DIR) / "docker-compose.prod.yml"


def _backend_routers() -> dict[str, dict[str, str]]:
    labels = yaml.safe_load(COMPOSE_PROD.read_text())["services"]["backend"]["labels"]
    routers: dict[str, dict[str, str]] = {}
    for label in labels:
        key, _, value = label.partition("=")
        match = re.fullmatch(r"traefik\.http\.routers\.([\w-]+)\.(rule|middlewares|priority)", key)
        if match:
            routers.setdefault(match.group(1), {})[match.group(2)] = value
    return routers


def _routers_matching(path_prefix: str) -> dict[str, dict[str, str]]:
    return {
        name: router
        for name, router in _backend_routers().items()
        if f"PathPrefix(`{path_prefix}`)" in router.get("rule", "")
    }


class TraefikRoutesTests(SimpleTestCase):
    def test_admin_keeps_basicauth(self):
        admin = _routers_matching("/admin")
        self.assertTrue(admin)
        for name, router in admin.items():
            self.assertIn("admin-auth@file", router["middlewares"], name)

    def test_company_portal_has_no_basicauth(self):
        portal = _routers_matching("/empresas")
        self.assertTrue(portal)
        for name, router in portal.items():
            self.assertNotIn("admin-auth@file", router["middlewares"], name)

    def test_company_portal_is_rate_limited(self):
        for name, router in _routers_matching("/empresas").items():
            self.assertRegex(router["middlewares"], r"rate-limit@file", name)

    def test_login_routes_keep_brute_force_rate_limit_and_win_priority(self):
        login = _routers_matching("/empresas/login")
        self.assertEqual(len(login), 1)
        (router,) = login.values()
        self.assertIn("login-rate-limit@file", router["middlewares"])
        portal_priorities = [
            int(r.get("priority", 0))
            for n, r in _routers_matching("/empresas").items()
            if "/empresas/login" not in r["rule"]
        ]
        self.assertGreater(int(router["priority"]), max(portal_priorities))
