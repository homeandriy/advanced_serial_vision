from __future__ import annotations

import secrets
from collections.abc import Callable

from serial_vision.warehouse.inventory import InventoryRepository
from serial_vision.warehouse.security import Role, WarehouseError, text


class WarehouseService:
    def __init__(self, repository: InventoryRepository, bootstrap_key: str | None = None) -> None:
        self.repository, self.bootstrap_key = repository, bootstrap_key

    def invoke(self, action: str, data: dict[str, object], token: str = "") -> dict[str, object]:
        repo = self.repository
        if action == "status":
            return {
                "initialized": repo.initialized(),
                "bootstrap_required": self.bootstrap_key is not None,
            }
        if action == "bootstrap":
            if self.bootstrap_key is not None and not secrets.compare_digest(
                text(data, "bootstrap_key", 256, False), self.bootstrap_key
            ):
                raise WarehouseError("wh_bootstrap_key", 403)
            return repo.bootstrap(data)
        if action == "login":
            return repo.login(data)
        actor = repo.authorize(token)
        if actor.must_change and action not in {"me", "change_password", "logout"}:
            raise WarehouseError("wh_password_change_required", 403)
        if actor.kind == "api" and action in {"change_password"}:
            raise WarehouseError("wh_forbidden", 403)
        admin_actions = {
            "users",
            "create_user",
            "update_user",
            "reset_password",
            "issue_token",
            "tokens",
            "revoke_token",
            "save_translation",
            "audits",
        }
        manage_actions = {
            "save_warehouse",
            "save_responsible",
            "import_warehouses",
            "save_model",
            "save_person",
        }
        if action in admin_actions and (actor.role != Role.ADMIN or actor.scope != "admin"):
            raise WarehouseError("wh_forbidden", 403)
        if action in manage_actions and actor.role == Role.STOREKEEPER:
            raise WarehouseError("wh_forbidden", 403)
        commands: dict[str, Callable[[], dict[str, object]]] = {
            "me": lambda: repo.me(actor),
            "logout": lambda: repo.logout(actor),
            "change_password": lambda: repo.change_password(actor, data),
            "users": repo.users,
            "create_user": lambda: repo.create_user(actor, data),
            "update_user": lambda: repo.update_user(actor, data),
            "reset_password": lambda: repo.reset_password(actor, data),
            "warehouses": lambda: repo.warehouses(actor),
            "people": lambda: repo.people(actor),
            "save_person": lambda: repo.save_person(actor, data),
            "save_warehouse": lambda: repo.save_warehouse(actor, data),
            "save_responsible": lambda: repo.save_responsible(actor, data),
            "responsible_history": lambda: repo.responsible_history(actor, data),
            "balances": lambda: repo.balances(actor, data),
            "movements": lambda: repo.movements(actor, data),
            "move": lambda: repo.move(actor, data),
            "models": repo.models,
            "save_model": lambda: repo.save_model(actor, data),
            "import_warehouses": lambda: repo.import_warehouses(actor, data),
            "translations": repo.translations,
            "save_translation": lambda: repo.save_translation(actor, data),
            "issue_token": lambda: repo.issue_token(actor, data),
            "tokens": repo.tokens,
            "revoke_token": lambda: repo.revoke_token(actor, data),
            "audits": repo.audits,
        }
        handler = commands.get(action)
        if handler is None:
            raise WarehouseError("wh_not_found", 404)
        return handler()
