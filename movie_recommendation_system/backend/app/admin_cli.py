"""Interactive provisioning commands for isolated administrator accounts."""

import click

from .admin_service import record_audit, revoke_admin_tokens
from .extensions import bcrypt, db
from .models import AdminAccount


def register_admin_commands(app):
    @app.cli.command("create-admin")
    @click.option("--email", prompt="Administrator email")
    @click.option("--name", prompt="Display name")
    @click.password_option(confirmation_prompt=True)
    def create_admin(email, name, password):
        """Create or securely re-provision an administrator account."""
        email = email.strip().lower()
        name = name.strip()
        if "@" not in email or not name:
            raise click.ClickException("A valid email and display name are required")
        if len(password) < 12:
            raise click.ClickException("Administrator passwords require 12 characters")

        admin = AdminAccount.query.filter_by(email=email).first()
        action = "admin.reprovisioned" if admin else "admin.provisioned"
        if admin is None:
            admin = AdminAccount(email=email, display_name=name, password_hash="")
            db.session.add(admin)
            db.session.flush()
        admin.display_name = name
        admin.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        admin.is_active = True
        admin.password_reset_required = False
        revoke_admin_tokens(admin)
        record_audit(admin.id, action)
        db.session.commit()
        click.echo(f"Administrator ready: {admin.email}")
